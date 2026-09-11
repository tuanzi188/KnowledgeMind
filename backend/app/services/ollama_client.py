import json
import asyncio
import logging
from typing import Optional, AsyncIterator

import httpx

from app.config import OLLAMA_CONFIG
from app.services.resilience import (
    circuit_breaker_registry,
    retry_with_backoff,
    CircuitBreakerOpenError,
)

logger = logging.getLogger(__name__)

# 可重试的 HTTP 异常
_RETRYABLE_ERRORS = (httpx.HTTPStatusError, httpx.ConnectError, httpx.TimeoutException)


class OllamaClient:
    def __init__(self):
        self.base_url = OLLAMA_CONFIG["base_url"]
        self.chat_model = OLLAMA_CONFIG["chat_model"]
        self.embed_model = OLLAMA_CONFIG["embedding_model"]
        self.default_max_tokens = OLLAMA_CONFIG["max_tokens"]
        self.default_temperature = OLLAMA_CONFIG["temperature"]
        self._client = httpx.AsyncClient(timeout=120.0)
        self._breaker = circuit_breaker_registry.get_or_create(
            name="ollama_api",
            failure_threshold=5,
            recovery_timeout=30.0,
        )
        logger.info(
            "Ollama client initialized: %s | chat=%s | embed=%s",
            self.base_url,
            self.chat_model,
            self.embed_model,
        )

    async def close(self):
        await self._client.aclose()

    async def chat(
        self,
        messages: list[dict],
        reasoning_mode: str = "non_think",
        temperature: float = 0.1,
        max_tokens: Optional[int] = None,
    ) -> tuple[str, Optional[str], dict]:
        """带熔断器 + 退避重试的 Ollama chat 调用"""
        self._breaker.before_call()
        try:
            result = await retry_with_backoff(
                lambda: self._chat_impl(messages, reasoning_mode, temperature, max_tokens),
                max_retries=3,
                base_delay=0.5,
                retryable_exceptions=_RETRYABLE_ERRORS,
            )
            self._breaker.on_success()
            return result
        except CircuitBreakerOpenError:
            raise
        except Exception as e:
            self._breaker.on_failure()
            raise

    async def _chat_impl(
        self,
        messages: list[dict],
        reasoning_mode: str = "non_think",
        temperature: float = 0.1,
        max_tokens: Optional[int] = None,
    ) -> tuple[str, Optional[str], dict]:
        max_tokens = max_tokens or self.default_max_tokens
        url = f"{self.base_url}/chat/completions"

        payload = {
            "model": self.chat_model,
            "messages": messages,
            "temperature": temperature or self.default_temperature,
            "max_tokens": max_tokens,
            "stream": False,
        }

        try:
            response = await self._client.post(url, json=payload)
            response.raise_for_status()
            data = response.json()

            choice = data.get("choices", [{}])[0]
            message = choice.get("message", {})
            content = message.get("content", "")
            reasoning = message.get("reasoning_content", None)

            usage = data.get("usage", {})
            usage_info = {
                "provider": "ollama",
                "model": self.chat_model,
                "prompt_tokens": usage.get("prompt_tokens", 0),
                "completion_tokens": usage.get("completion_tokens", 0),
                "total_tokens": usage.get("total_tokens", 0),
            }

            return content, reasoning, usage_info

        except httpx.HTTPStatusError as e:
            logger.error(
                "Ollama chat error: %s %s",
                e.response.status_code,
                e.response.text[:500],
            )
            raise RuntimeError(
                "Ollama 请求失败 (HTTP %s): 请确认 ollama 正在运行且已下载 %s 模型"
                % (e.response.status_code, self.chat_model)
            )
        except httpx.ConnectError:
            raise RuntimeError(
                "无法连接 Ollama (%s)。\n"
                "请确认：\n"
                "1. Ollama 已安装并启动 (ollama serve)\n"
                "2. 已下载模型: ollama pull %s"
                % (self.base_url, self.chat_model)
            )
        except Exception as e:
            logger.error("Ollama chat unexpected error: %s", e)
            raise RuntimeError("Ollama 调用异常: %s" % e)

    async def simple_query(
        self, query: str, system_prompt: Optional[str] = None
    ) -> tuple[str, Optional[str], dict]:
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": query})
        return await self.chat(messages, reasoning_mode="non_think", max_tokens=2048)

    async def fallback_query(
        self, query: str, system_prompt: Optional[str] = None
    ) -> tuple[str, Optional[str], dict]:
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": query})
        return await self.chat(messages, reasoning_mode="non_think", temperature=0.5, max_tokens=4096)

    async def rag_query(
        self, query: str, context: str, reasoning_mode: str = "think_high"
    ) -> tuple[str, Optional[str], dict]:
        system_prompt = (
            "你是一个企业知识库AI助手。请基于提供的参考资料回答问题。\n"
            "要求：\n"
            "1. 每句关键信息必须标注引用来源，格式为 [引用: 文档标题, 页码]\n"
            "2. 如果参考资料不足以回答问题，明确说'根据现有资料无法确定'\n"
            "3. 回答结构化呈现，使用编号列表、表格等方式\n"
            "4. 不要编造信息，不要添加资料中没有的内容"
        )
        user_prompt = f"参考资料：\n{context}\n\n问题：{query}"
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]
        return await self.chat(messages, reasoning_mode="non_think", max_tokens=4096)

    async def chat_stream(
        self,
        messages: list[dict],
        reasoning_mode: str = "non_think",
        temperature: float = 0.1,
        max_tokens: Optional[int] = None,
        result_holder: Optional[dict] = None,
    ) -> AsyncIterator[str]:
        """带熔断器 + reasoning_content 采集的流式调用"""
        self._breaker.before_call()
        max_tokens = max_tokens or self.default_max_tokens
        url = f"{self.base_url}/chat/completions"
        payload = {
            "model": self.chat_model,
            "messages": messages,
            "temperature": temperature or self.default_temperature,
            "max_tokens": max_tokens,
            "stream": True,
        }
        reasoning_parts: list[str] = []

        try:
            async with self._client.stream("POST", url, json=payload) as response:
                response.raise_for_status()
                async for line in response.aiter_lines():
                    if not line:
                        continue
                    normalized_line = line.strip()
                    if not normalized_line.startswith("data:"):
                        continue
                    data_payload = normalized_line[5:].strip()
                    if data_payload == "[DONE]":
                        break
                    try:
                        event_object = json.loads(data_payload)
                    except json.JSONDecodeError:
                        continue
                    choice_object = (event_object.get("choices") or [{}])[0]
                    delta_object = choice_object.get("delta", {})
                    reasoning_content = delta_object.get("reasoning_content", "")
                    if reasoning_content:
                        reasoning_parts.append(reasoning_content)
                    token_text = delta_object.get("content", "")
                    if token_text:
                        yield token_text
            self._breaker.on_success()
            if result_holder is not None:
                result_holder["reasoning_content"] = "".join(reasoning_parts)
                result_holder["provider"] = "ollama"
        except httpx.HTTPStatusError as e:
            self._breaker.on_failure()
            logger.error(
                "Ollama stream error: %s %s",
                e.response.status_code,
                e.response.text[:500],
            )
            raise RuntimeError("Ollama 流式请求失败 (HTTP %s)" % e.response.status_code)
        except httpx.ConnectError:
            self._breaker.on_failure()
            raise RuntimeError("无法连接 Ollama (%s)。请确认 Ollama 正在运行。" % self.base_url)
        except Exception as e:
            self._breaker.on_failure()
            logger.error("Ollama stream unexpected error: %s", e)
            raise RuntimeError("Ollama 流式调用异常: %s" % e)

    async def rag_query_stream(
        self,
        query: str,
        context: str,
        reasoning_mode: str = "think_high",
        result_holder: Optional[dict] = None,
    ) -> AsyncIterator[str]:
        system_prompt = (
            "你是一个企业知识库AI助手。请基于提供的参考资料回答问题。\n"
            "要求：\n"
            "1. 每句关键信息必须标注引用来源，格式为 [引用: 文档标题, 页码]\n"
            "2. 如果参考资料不足以回答问题，明确说'根据现有资料无法确定'\n"
            "3. 回答结构化呈现，使用编号列表、表格等方式\n"
            "4. 不要编造信息，不要添加资料中没有的内容"
        )
        user_prompt = f"参考资料：\n{context}\n\n问题：{query}"
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]
        async for token in self.chat_stream(
            messages,
            reasoning_mode="non_think",
            max_tokens=4096,
            result_holder=result_holder,
        ):
            yield token

    async def classify_intent(self, query: str) -> dict:
        prompt = (
            f"分析以下查询的意图，返回JSON格式：\n"
            f"查询: {query}\n"
            f"请分析：\n"
            f"1. query_type: 枚举值 [simple_fact, complex_analysis, document_summary, relationship_query, comparison]\n"
            f"2. reasoning_needed: 布尔值, 是否需要深度推理\n"
            f"3. complexity: 1-5 的复杂度评分\n"
            f"4. estimated_docs_needed: 预估需要的文档数量\n\n"
            f"只返回JSON，不要其他内容。"
        )
        content, _, _ = await self.simple_query(prompt)
        try:
            cleaned = content.strip().removeprefix("```json").removesuffix("```").strip()
            return json.loads(cleaned)
        except json.JSONDecodeError:
            return {"query_type": "complex_analysis", "reasoning_needed": True, "complexity": 3, "estimated_docs_needed": 5}

    async def rewrite_query(self, query: str) -> list[str]:
        prompt = (
            "请将用户问题改写为适合企业知识库检索的查询表达。\n"
            "要求：\n"
            "1. 保留原意，不要引入原问题没有的新事实\n"
            "2. 输出 2 到 3 条更适合检索的短查询\n"
            "3. 覆盖简称、正式名称、关键词表达\n"
            "4. 只返回 JSON 数组，例如 [\"改写1\", \"改写2\"]\n\n"
            f"用户问题：{query}"
        )
        content, _, _ = await self.simple_query(prompt)
        try:
            cleaned = content.strip().removeprefix("```json").removeprefix("```").removesuffix("```").strip()
            parsed_queries = json.loads(cleaned)
            if isinstance(parsed_queries, list):
                normalized_queries = []
                for parsed_query in parsed_queries:
                    if isinstance(parsed_query, str):
                        cleaned_query = parsed_query.strip()
                        if cleaned_query and cleaned_query not in normalized_queries:
                            normalized_queries.append(cleaned_query)
                return normalized_queries[:3]
        except json.JSONDecodeError:
            return []
        return []

    def select_reasoning_mode(self, intent: dict) -> str:
        complexity = intent.get("complexity", 1)
        reasoning_needed = intent.get("reasoning_needed", False)
        query_type = intent.get("query_type", "simple_fact")

        if query_type == "simple_fact" and complexity <= 2 and not reasoning_needed:
            return "non_think"
        elif query_type in ("relationship_query", "comparison") or complexity >= 4:
            return "think_max"
        else:
            return "think_high"

    async def get_embedding(self, text: str) -> list[float]:
        """带熔断器 + 退避重试的 embedding 调用"""
        self._breaker.before_call()
        url = f"{self.base_url}/embeddings"
        payload = {"model": self.embed_model, "input": text}
        try:
            result = await retry_with_backoff(
                lambda: self._get_embedding_impl(url, payload),
                max_retries=3,
                base_delay=0.5,
                retryable_exceptions=_RETRYABLE_ERRORS,
            )
            self._breaker.on_success()
            return result
        except CircuitBreakerOpenError:
            raise
        except Exception as e:
            self._breaker.on_failure()
            raise

    async def _get_embedding_impl(self, url: str, payload: dict) -> list[float]:
        try:
            response = await self._client.post(url, json=payload)
            response.raise_for_status()
            data = response.json()
            return data["data"][0]["embedding"]
        except httpx.ConnectError:
            raise RuntimeError(
                "无法连接 Ollama (%s)。请确认 Ollama 正在运行。" % self.base_url
            )
        except Exception as e:
            logger.error("Ollama embedding error: %s", e)
            raise RuntimeError("Ollama Embedding 失败: %s" % e)

    async def get_embeddings_batch(self, texts: list[str]) -> list[list[float]]:
        # 并发请求 Ollama embedding 接口，避免逐条串行等待
        return await asyncio.gather(*[self.get_embedding(text) for text in texts])


ollama_client = OllamaClient()
