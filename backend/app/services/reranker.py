import re
import asyncio
import logging
from collections import Counter
from typing import List, Optional

logger = logging.getLogger(__name__)


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
                logger.info("BGE Reranker model not in cache, downloading (timeout=60s)...")
                # Download with timeout to avoid blocking startup
                import asyncio
                try:
                    self._reranker_tokenizer = await asyncio.wait_for(
                        asyncio.to_thread(
                            AutoTokenizer.from_pretrained,
                            "BAAI/bge-reranker-base",
                        ),
                        timeout=60.0,
                    )
                    self._reranker_model = await asyncio.wait_for(
                        asyncio.to_thread(
                            AutoModelForSequenceClassification.from_pretrained,
                            "BAAI/bge-reranker-base",
                        ),
                        timeout=60.0,
                    )
                except asyncio.TimeoutError:
                    logger.warning("BGE Reranker model download timed out, L2 will fallback to L1")
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

            overlap = sum(1 for t in query_tokens if t in "".join(content_tokens))
            keyword_density = len(query_tokens & set(content_tokens)) / max(len(query_tokens), 1)
            base_score = c.get("rrf_score", c.get("score", 0))
            c["rerank_score"] = base_score * 0.5 + keyword_density * 0.3 + (overlap / max(len(content), 1)) * 0.2
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
        total_chars = 0
        char_budget = self._estimate_chars_for_tokens(max_tokens)
        seen_ids = set()
        per_document_chunk_counter: dict[str, int] = {}
        max_chunks_per_document = 2

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

            if total_chars + len(content) <= char_budget:
                used_docs.append(doc)
                total_chars += len(content)
                per_document_chunk_counter[document_key] = current_document_chunk_count + 1
            elif len(content) > char_budget // 3:
                truncated = content[:char_budget // 3]
                if total_chars + len(truncated) <= char_budget:
                    doc = {**doc, "content": truncated + "...[截断]"}
                    used_docs.append(doc)
                    total_chars += len(truncated)
                    per_document_chunk_counter[document_key] = current_document_chunk_count + 1

            if total_chars >= char_budget:
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

    @staticmethod
    def _estimate_chars_for_tokens(max_tokens: int) -> int:
        return int(max_tokens * 3.2)


reranker = Reranker()
