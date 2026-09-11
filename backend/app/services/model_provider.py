import logging
from typing import Optional, List, AsyncIterator

from app.config import MODEL_MODE, MODEL_PROVIDER
from app.services.deepseek import deepseek_client
from app.services.qwen_client import qwen_client
from app.services.ollama_client import ollama_client

logger = logging.getLogger(__name__)


def _resolve_provider():
    normalized_mode = (MODEL_MODE or "api").strip().lower()
    if normalized_mode in {"ollama", "local"}:
        return ollama_client
    if MODEL_PROVIDER == "qwen":
        return qwen_client
    return deepseek_client


def _resolve_reasoning_mode(reasoning_mode: str) -> str:
    normalized_mode = (MODEL_MODE or "deepseek").strip().lower()
    if normalized_mode in {"ollama", "local"}:
        mode_mapping = {
            "flash": "non_think",
            "pro": "think_high",
            "think_high": "think_high",
            "think_max": "think_max",
            "non_think": "non_think",
        }
        return mode_mapping.get(reasoning_mode, "think_high")
    return reasoning_mode


async def chat(
    messages: List[dict],
    reasoning_mode: str = "flash",
    temperature: float = 0.1,
    max_tokens: Optional[int] = None,
) -> tuple[str, Optional[str], dict]:
    provider_instance = _resolve_provider()
    normalized_reasoning_mode = _resolve_reasoning_mode(reasoning_mode)
    return await provider_instance.chat(messages, normalized_reasoning_mode, temperature, max_tokens)


async def chat_stream(
    messages: List[dict],
    reasoning_mode: str = "flash",
    temperature: float = 0.1,
    max_tokens: Optional[int] = None,
    result_holder: Optional[dict] = None,
) -> AsyncIterator[str]:
    provider_instance = _resolve_provider()
    normalized_reasoning_mode = _resolve_reasoning_mode(reasoning_mode)
    async for token in provider_instance.chat_stream(
        messages,
        normalized_reasoning_mode,
        temperature,
        max_tokens,
        result_holder=result_holder,
    ):
        yield token


async def simple_query(
    query: str, system_prompt: Optional[str] = None
) -> tuple[str, Optional[str], dict]:
    provider_instance = _resolve_provider()
    return await provider_instance.simple_query(query, system_prompt)


async def fallback_query(
    query: str, system_prompt: Optional[str] = None
) -> tuple[str, Optional[str], dict]:
    provider_instance = _resolve_provider()
    fallback_handler = getattr(provider_instance, "fallback_query", None)
    if callable(fallback_handler):
        return await fallback_handler(query, system_prompt)
    return await provider_instance.simple_query(query, system_prompt)


async def rag_query(
    query: str, context: str, reasoning_mode: str = "pro"
) -> tuple[str, Optional[str], dict]:
    provider_instance = _resolve_provider()
    normalized_reasoning_mode = _resolve_reasoning_mode(reasoning_mode)
    return await provider_instance.rag_query(query, context, normalized_reasoning_mode)


async def rag_query_stream(
    query: str,
    context: str,
    reasoning_mode: str = "pro",
    result_holder: Optional[dict] = None,
) -> AsyncIterator[str]:
    provider_instance = _resolve_provider()
    normalized_reasoning_mode = _resolve_reasoning_mode(reasoning_mode)
    async for token in provider_instance.rag_query_stream(
        query,
        context,
        normalized_reasoning_mode,
        result_holder=result_holder,
    ):
        yield token


async def classify_intent(query: str) -> dict:
    provider_instance = _resolve_provider()
    return await provider_instance.classify_intent(query)


async def rewrite_query(query: str) -> List[str]:
    provider_instance = _resolve_provider()
    rewrite_handler = getattr(provider_instance, "rewrite_query", None)
    if callable(rewrite_handler):
        return await rewrite_handler(query)
    return []


def select_reasoning_mode(intent: dict) -> str:
    provider_instance = _resolve_provider()
    provider_selected_mode = provider_instance.select_reasoning_mode(intent)
    normalized_mode = (MODEL_MODE or "deepseek").strip().lower()
    if normalized_mode in {"ollama", "local"}:
        reverse_mode_mapping = {
            "non_think": "flash",
            "think_high": "pro",
            "think_max": "pro",
        }
        return reverse_mode_mapping.get(provider_selected_mode, "pro")
    return provider_selected_mode
