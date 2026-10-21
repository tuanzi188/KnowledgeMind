"""托管重排客户端（阿里云百炼 qwen3.7-text-rerank）。

接口形态与百炼的 Cohere 兼容扁平接口一致：

    POST {api_base_url}
    {"model": "...", "query": "...", "documents": [...], "top_n": 5}
    -> {"results": [{"index": 0, "relevance_score": 0.93}, ...]}

返回 (原始下标, 分数) 列表；任何一步失败（未配置 key / 超时 / 非 200 / 报文异常）
都返回 None，由调用方降级到本地 Cross-Encoder，绝不伪造分数。
"""
import logging
from typing import List, Optional, Sequence, Tuple

import httpx

from app.config import RERANK_CONFIG

logger = logging.getLogger(__name__)

# 最近一次调用结果，供 /health/deep 暴露，避免“配了 key 但接口挂了”被静默降级。
_LAST_CALL: dict = {"ok": None, "detail": "尚未调用"}


def is_configured() -> bool:
    """key / 地址 / 模型名三者齐备才认为可用。"""
    return bool(
        RERANK_CONFIG.get("api_key")
        and RERANK_CONFIG.get("api_base_url")
        and RERANK_CONFIG.get("api_model")
    )


def describe() -> dict:
    """健康检查用：把当前生效的是哪一档摆出来，避免降级静默。"""
    if is_configured():
        return {
            "status": "healthy",
            "mode": "remote",
            "model": RERANK_CONFIG.get("api_model"),
            "last_call": dict(_LAST_CALL),
        }
    return {
        "status": "degraded",
        "mode": "local",
        "model": "BAAI/bge-reranker-base",
        "reason": "RERANK_API_KEY/ALI_API_KEY 未配置，走本地 Cross-Encoder",
    }


def _extract_results(payload: object) -> List[dict]:
    """兼容 Cohere 扁平接口（results）与 DashScope 原生接口（output.results）。"""
    if not isinstance(payload, dict):
        return []
    results = payload.get("results")
    if not results:
        output = payload.get("output")
        if isinstance(output, dict):
            results = output.get("results")
    return results if isinstance(results, list) else []


async def remote_rerank(
    query: str,
    documents: Sequence[str],
    top_n: int,
) -> Optional[List[Tuple[int, float]]]:
    """调用托管重排，成功返回 [(下标, 分数)]，失败返回 None。"""
    if not documents or not is_configured():
        return None

    payload = {
        "model": RERANK_CONFIG["api_model"],
        "query": query,
        "documents": list(documents),
        "top_n": max(1, min(top_n, len(documents))),
    }
    headers = {
        "Authorization": f"Bearer {RERANK_CONFIG['api_key']}",
        "Content-Type": "application/json",
    }

    try:
        async with httpx.AsyncClient(timeout=RERANK_CONFIG["timeout_seconds"]) as client:
            response = await client.post(
                RERANK_CONFIG["api_base_url"], json=payload, headers=headers
            )
    except Exception as exc:  # noqa: BLE001 - 网络异常一律降级
        _LAST_CALL.update(ok=False, detail=f"请求失败: {exc}")
        logger.warning("[rerank-api] 请求失败，降级到本地 Cross-Encoder: %s", exc)
        return None

    if response.status_code != 200:
        _LAST_CALL.update(ok=False, detail=f"HTTP {response.status_code}")
        logger.warning(
            "[rerank-api] status=%s preview=%s，降级到本地 Cross-Encoder",
            response.status_code,
            response.text[:300],
        )
        return None

    try:
        results = _extract_results(response.json())
    except Exception as exc:  # noqa: BLE001
        _LAST_CALL.update(ok=False, detail=f"响应解析失败: {exc}")
        logger.warning("[rerank-api] 响应解析失败: %s", exc)
        return None

    scored: List[Tuple[int, float]] = []
    for item in results:
        if not isinstance(item, dict):
            continue
        try:
            index = int(item.get("index", -1))
            score = float(item.get("relevance_score", 0.0))
        except (TypeError, ValueError):
            continue
        if 0 <= index < len(documents):
            scored.append((index, score))

    if not scored:
        _LAST_CALL.update(ok=False, detail="返回结果为空")
        logger.warning("[rerank-api] 返回结果为空，降级到本地 Cross-Encoder")
        return None

    scored.sort(key=lambda pair: pair[1], reverse=True)
    _LAST_CALL.update(ok=True, detail=f"返回 {len(scored)} 条")
    return scored
