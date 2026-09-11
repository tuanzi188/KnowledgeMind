import asyncio
from typing import List, Optional
import logging

from app.config import RETRIEVAL_CONFIG
from app.core.cache import TimedLRUCache
from app.services.vector_store import vector_store
from app.services.keyword_search import get_bm25_searcher
from app.services.graph_search import graph_searcher
from app.services.filter_utils import match_filters

logger = logging.getLogger(__name__)

# 检索结果缓存：相同查询条件避免重复访问向量/BM25/图谱
_retrieval_cache = TimedLRUCache(maxsize=256, ttl_seconds=300)


class HybridRetriever:
    def __init__(self):
        self.weight_profiles = {
            "概念解释": {"vector": 0.6, "keyword": 0.3, "graph": 0.1},
            "精确查找": {"vector": 0.2, "keyword": 0.7, "graph": 0.1},
            "关系推理": {"vector": 0.2, "keyword": 0.2, "graph": 0.6},
            "综合分析": {"vector": 0.4, "keyword": 0.3, "graph": 0.3},
            "对比分析": {"vector": 0.4, "keyword": 0.4, "graph": 0.2},
            "文档摘要": {"vector": 0.5, "keyword": 0.4, "graph": 0.1},
        }
        # 纯关键词降级权重（向量检索不可用时）
        self._keyword_only_weights = {"vector": 0.0, "keyword": 0.9, "graph": 0.1}

    async def retrieve(
        self,
        query: str,
        filters: Optional[dict] = None,
        top_k: int = 10,
        query_type: str = "综合分析",
    ) -> List[dict]:
        if await vector_store.count() == 0:
            return []

        cached_results = _retrieval_cache.get(query, top_k, filters=filters, query_type=query_type)
        if cached_results is not None:
            return cached_results

        # 三种检索源相互独立，使用 asyncio.gather 并行执行
        vector_results, keyword_results, graph_results = await asyncio.gather(
            self._vector_search_safe(query, top_k * 2, filters),
            asyncio.to_thread(self._keyword_search_safe, query, top_k * 2, filters),
            self._graph_search_safe(query, top_k, filters),
        )

        if vector_results is None:
            logger.warning("向量检索不可用，降级为纯关键词+图谱检索")
            weights = self._keyword_only_weights
        else:
            weights = self.weight_profiles.get(query_type, self.weight_profiles["综合分析"])

        fused = self.rrf_fuse(
            [vector_results or [], keyword_results or [], graph_results or []],
            weights=[weights["vector"], weights["keyword"], weights["graph"]],
            top_k=top_k,
        )

        results = self.deduplicate_and_filter(fused, filters)
        _retrieval_cache.set(results, query, top_k, filters=filters, query_type=query_type)
        return results

    async def _vector_search_safe(
        self, query: str, top_k: int, filters: Optional[dict]
    ) -> Optional[List[dict]]:
        """安全的向量检索：失败时返回 None，触发降级"""
        try:
            results = await vector_store.similarity_search(
                query_text=query,
                top_k=top_k,
                filters=filters,
            )
            for r in results:
                r["source"] = "vector"
            return results
        except Exception as e:
            logger.warning("向量检索失败 (降级处理): %s", e)
            return None

    def _keyword_search_safe(
        self, query: str, top_k: int, filters: Optional[dict]
    ) -> Optional[List[dict]]:
        """安全的关键词检索：失败时返回 None"""
        try:
            bm25 = get_bm25_searcher()
            return bm25.search(query, top_k=top_k, filters=filters)
        except Exception as e:
            logger.warning("关键词检索失败 (降级处理): %s", e)
            return None

    async def _graph_search_safe(
        self, query: str, top_k: int, filters: Optional[dict]
    ) -> Optional[List[dict]]:
        """安全的图谱检索：失败时返回 None"""
        try:
            return await graph_searcher.search(query, top_k=top_k, filters=filters)
        except Exception as e:
            logger.warning("图谱检索失败 (降级处理): %s", e)
            return None

    def rrf_fuse(
        self,
        result_sets: List[List[dict]],
        weights: Optional[List[float]] = None,
        top_k: int = 10,
    ) -> List[dict]:
        k = RETRIEVAL_CONFIG["rrf_k"]
        scores: dict[str, dict] = {}

        if weights is None:
            weights = [1.0] * len(result_sets)

        for set_idx, results in enumerate(result_sets):
            weight = weights[set_idx] if set_idx < len(weights) else 1.0
            for rank, doc in enumerate(results):
                cid = doc.get("chunk_id", str(rank))
                if cid not in scores:
                    scores[cid] = {
                        **doc,
                        "rrf_score": 0.0,
                        "source_scores": {},
                    }
                scores[cid]["rrf_score"] += weight * (1.0 / (k + rank + 1))
                scores[cid]["source_scores"][doc.get("source", "unknown")] = doc.get("score", 0)

        ranked = sorted(scores.values(), key=lambda x: x["rrf_score"], reverse=True)
        for i, item in enumerate(ranked):
            item["rank"] = i + 1

        return ranked[:top_k]

    def deduplicate_and_filter(
        self,
        results: List[dict],
        filters: Optional[dict] = None,
    ) -> List[dict]:
        seen_ids = set()
        unique = []
        for r in results:
            cid = r.get("chunk_id", "")
            if cid and cid not in seen_ids:
                seen_ids.add(cid)
                if filters:
                    metadata = r.get("metadata", {})
                    if not match_filters(metadata, filters):
                        continue
                unique.append(r)
        return unique

    def query_type_to_profile(self, query_type: str) -> str:
        type_map = {
            "simple_fact": "精确查找",
            "complex_analysis": "综合分析",
            "document_summary": "文档摘要",
            "relationship_query": "关系推理",
            "comparison": "对比分析",
        }
        return type_map.get(query_type, "综合分析")


hybrid_retriever = HybridRetriever()


async def hybrid_search(
    query: str,
    top_k: int = 10,
    filters: Optional[dict] = None,
    query_type: str = "综合分析",
) -> List[dict]:
    return await hybrid_retriever.retrieve(
        query=query,
        filters=filters,
        top_k=top_k,
        query_type=query_type,
    )
