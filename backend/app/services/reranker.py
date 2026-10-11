import re
import asyncio
import logging
from collections import Counter
from typing import List, Optional

logger = logging.getLogger(__name__)


_CJK_RANGES = (
    ("\u4e00", "\u9fff"),   # CJK 统一表意文字
    ("\u3400", "\u4dbf"),   # 扩展 A
    ("\u3040", "\u30ff"),   # 日文假名
    ("\uac00", "\ud7af"),   # 韩文音节
)


def estimate_tokens(text: str) -> int:
    """按字符构成估算 token 数：CJK 约 1 token/字，其余约 1 token/4 字符。

    原先统一按 3.2 字/token 折算，那是英文经验值。中文一个汉字基本就是 1 个
    token，用 3.2 会低估 2~3 倍，按 max_tokens 组装出的上下文实际会远超预算。
    """
    if not text:
        return 0
    cjk = 0
    for ch in text:
        if any(low <= ch <= high for low, high in _CJK_RANGES):
            cjk += 1
    other = len(text) - cjk
    return cjk + max(1, round(other / 4)) if other else cjk


def _truncate_to_tokens(text: str, token_cap: int) -> str:
    """按估算 token 数截断，二分查找保证结果与 estimate_tokens 口径一致。"""
    if estimate_tokens(text) <= token_cap:
        return text
    low, high = 0, len(text)
    while low < high:
        mid = (low + high + 1) // 2
        if estimate_tokens(text[:mid]) <= token_cap:
            low = mid
        else:
            high = mid - 1
    return text[:low]


class Reranker:
    def __init__(self):
        self._reranker_model = None
        self._model_loaded = False
        self._lock = asyncio.Lock()

    async def warmup(self):
        try:
            from transformers import AutoTokenizer, AutoModelForSequenceClassification
            import torch
            
            logger.info("Warming up BGE Reranker model...")
            
            # Try loading from cache first (fast)
            try:
                self._reranker_tokenizer = AutoTokenizer.from_pretrained(
                    "BAAI/bge-reranker-base",
                    local_files_only=True,
                )
                self._reranker_model = AutoModelForSequenceClassification.from_pretrained(
                    "BAAI/bge-reranker-base",
                    local_files_only=True,
                )
            except Exception:
                # 启动阶段只允许读本地缓存，绝不下载：asyncio.wait_for 无法取消
                # asyncio.to_thread 里已经跑起来的下载线程，一旦模型未缓存，启动会被
                # 无限期阻塞（冷启动实测卡死超过 2 分钟）。未缓存就跳过预热，L2 档在
                # 真正被用到时再懒加载。
                self._reranker_model = None
                logger.info(
                    "BGE Reranker not in local cache; skipping warmup, "
                    "L2 will load lazily on first use (L1 fallback until then)"
                )
                return
            
            self._reranker_model.eval()
            self._model_loaded = True
            logger.info("BGE Reranker model loaded successfully")
        except ImportError:
            logger.info("transformers not installed, L2 reranking will use L1 fallback")
        except Exception as e:
            logger.warning("BGE Reranker warmup failed: %s, L2 will fallback to L1", e)

    def _tokenize(self, text: str) -> list[str]:
        tokens = []
        for token in re.findall(r'[a-zA-Z0-9]+|[\u4e00-\u9fff]', text.lower()):
            if token.strip():
                tokens.append(token.strip())
        return tokens

    async def rerank(
        self,
        query: str,
        candidates: List[dict],
        top_k: int = 5,
        strategy: str = "auto",
    ) -> List[dict]:
        if not candidates:
            return []

        if len(candidates) <= top_k:
            for c in candidates:
                c["rerank_score"] = c.get("rrf_score", c.get("score", 0))
                c["rerank_level"] = "L0"
            return candidates

        if strategy == "auto":
            if len(candidates) <= 10:
                strategy = "l3"  # Use DeepSeek for small batches
            elif len(candidates) <= 30:
                strategy = "l2"  # Use Cross-Encoder
            else:
                strategy = "l1"  # Use heuristic

        if strategy == "l1":
            return self._heuristic_rerank(query, candidates, top_k)
        elif strategy == "l2":
            return await self._cross_encoder_rerank(query, candidates, top_k)
        elif strategy == "l3":
            return await self._deepseek_rerank(query, candidates, top_k)
        else:
            return self._heuristic_rerank(query, candidates, top_k)

    def _heuristic_rerank(self, query: str, candidates: List[dict], top_k: int) -> List[dict]:
        query_tokens = set(self._tokenize(query))
        if not query_tokens:
            return candidates[:top_k]

        for c in candidates:
            content = c.get("content", "")
            content_tokens = self._tokenize(content)
            if not content_tokens:
                c["rerank_score"] = c.get("rrf_score", c.get("score", 0))
                c["rerank_level"] = "L1"
                continue

            # 命中数用集合交集统计；原先写成 t in "".join(content_tokens) 是在拼接串上做子串
            # 匹配，会跨词边界误命中（如 "工伤" 命中 ["工","伤"] 拼接结果）。
            matched = query_tokens & set(content_tokens)
            keyword_density = len(matched) / max(len(query_tokens), 1)
            base_score = c.get("rrf_score", c.get("score", 0))
            c["rerank_score"] = base_score * 0.5 + keyword_density * 0.3 + (len(matched) / max(len(content), 1)) * 0.2
            c["rerank_level"] = "L1"

        candidates.sort(key=lambda x: x.get("rerank_score", 0), reverse=True)
        return candidates[:top_k]

    def _run_rerank_inference(self, pairs: list[list[str]]) -> list[float]:
        """在线程中执行 Cross-Encoder 的 tokenizer + model forward（CPU 密集型）。"""
        import torch
        with torch.no_grad():
            inputs = self._reranker_tokenizer(
                pairs, padding=True, truncation=True, return_tensors="pt", max_length=512
            )
            scores = self._reranker_model(**inputs, return_dict=True).logits.view(-1).float()
        return scores.tolist()

    async def _cross_encoder_rerank(self, query: str, candidates: List[dict], top_k: int) -> List[dict]:
        if not self._model_loaded:
            try:
                from transformers import AutoTokenizer, AutoModelForSequenceClassification
                import torch
                self._reranker_tokenizer = AutoTokenizer.from_pretrained(
                    "BAAI/bge-reranker-base"
                )
                self._reranker_model = AutoModelForSequenceClassification.from_pretrained(
                    "BAAI/bge-reranker-base"
                )
                self._reranker_model.eval()
                self._model_loaded = True
                logger.info("BGE Reranker model loaded")
            except ImportError:
                logger.warning("transformers not installed, falling back to L1 heuristic")
                return self._heuristic_rerank(query, candidates, top_k)
            except Exception as e:
                logger.warning("Failed to load BGE Reranker: %s, falling back to L1", e)
                return self._heuristic_rerank(query, candidates, top_k)

        try:
            pairs = [[query, c.get("content", "")[:400]] for c in candidates]
            async with self._lock:
                scores = await asyncio.to_thread(self._run_rerank_inference, pairs)

            for i, c in enumerate(candidates):
                c["rerank_score"] = float(scores[i])
                c["rerank_level"] = "L2"

            candidates.sort(key=lambda x: x.get("rerank_score", 0), reverse=True)
            return candidates[:top_k]
        except Exception as e:
            logger.error("Cross-Encoder rerank failed: %s", e)
            return self._heuristic_rerank(query, candidates, top_k)

    async def _deepseek_rerank(self, query: str, candidates: List[dict], top_k: int) -> List[dict]:
        from app.services.deepseek import deepseek_client

        top_n = min(len(candidates), 15)
        target = candidates[:top_n]

        prompt_parts = ["评估以下文档与查询的相关性（0-5分）：\n"]
        prompt_parts.append(f"查询: {query}\n")
        for i, c in enumerate(target, 1):
            content = c.get("content", "")[:300]
            prompt_parts.append(f"[{i}] {content}\n")
        prompt_parts.append("\n输出JSON格式: [{\"id\": 数字, \"score\": 数字, \"reason\": \"简短理由\"}]")
        prompt_parts.append("\n只输出JSON，不要其他内容。")

        try:
            content, reasoning, usage = await deepseek_client.simple_query(
                "\n".join(prompt_parts)
            )
            import json
            cleaned = content.strip().removeprefix("```json").removeprefix("```").removesuffix("```").strip()
            scores = json.loads(cleaned)

            score_map = {s.get("id", 0): s.get("score", 0) for s in scores}
            for i, c in enumerate(target, 1):
                c["rerank_score"] = score_map.get(i, 1.0) / 5.0 + c.get("rrf_score", c.get("score", 0)) * 0.3
                c["rerank_level"] = "L3"

            for c in candidates[top_n:]:
                c["rerank_score"] = c.get("rrf_score", c.get("score", 0))
                c["rerank_level"] = "L3-fallback"

        except Exception as e:
            logger.error("DeepSeek rerank failed: %s, falling back to L2 Cross-Encoder", e)
            try:
                return await self._cross_encoder_rerank(query, candidates, top_k)
            except Exception as e2:
                logger.error("Cross-Encoder fallback also failed: %s, using L1 heuristic", e2)
                return self._heuristic_rerank(query, candidates, top_k)

        candidates.sort(key=lambda x: x.get("rerank_score", 0), reverse=True)
        return candidates[:top_k]

    async def assemble_context(
        self,
        reranked: List[dict],
        max_tokens: int = 4000,
        overlap_tokens: int = 50,
    ) -> tuple[str, List[dict]]:
        if not reranked:
            return "", []

        used_docs = []
        used_tokens = 0
        seen_ids = set()
        per_document_chunk_counter: dict[str, int] = {}
        max_chunks_per_document = 2
        # 单个文档最多占预算的 1/3，避免一篇长文档挤掉其余候选
        single_doc_token_cap = max(max_tokens // 3, 1)

        for doc in reranked:
            chunk_id = doc.get("chunk_id", "")
            if chunk_id in seen_ids:
                continue
            seen_ids.add(chunk_id)

            content = doc.get("content", "")
            metadata = doc.get("metadata", {})
            document_key = str(
                metadata.get("document_id")
                or metadata.get("title")
                or metadata.get("filename")
                or chunk_id
            )
            current_document_chunk_count = per_document_chunk_counter.get(document_key, 0)
            if current_document_chunk_count >= max_chunks_per_document:
                continue

            content_tokens = estimate_tokens(content)

            if used_tokens + content_tokens <= max_tokens:
                used_docs.append(doc)
                used_tokens += content_tokens
                per_document_chunk_counter[document_key] = current_document_chunk_count + 1
            elif content_tokens > single_doc_token_cap:
                truncated = _truncate_to_tokens(content, single_doc_token_cap)
                truncated_tokens = estimate_tokens(truncated)
                if truncated and used_tokens + truncated_tokens <= max_tokens:
                    doc = {**doc, "content": truncated + "...[截断]"}
                    used_docs.append(doc)
                    used_tokens += truncated_tokens
                    per_document_chunk_counter[document_key] = current_document_chunk_count + 1

            if used_tokens >= max_tokens:
                break

        parts = []
        for i, doc in enumerate(used_docs, 1):
            metadata = doc.get("metadata", {})
            title = metadata.get("title", metadata.get("filename", "未知文档"))
            chunk_idx = metadata.get("chunk_index", i)
            page = metadata.get("page", metadata.get("page_number"))
            page_info = f", P{page}" if page else ""
            content = doc.get("content", "")
            parts.append(f"[{i}] {title} (段落{chunk_idx}{page_info}):\n{content}")

        return "\n\n---\n\n".join(parts), used_docs


reranker = Reranker()
