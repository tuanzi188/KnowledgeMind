"""KnowledgeMind MCP server（最小可用版）

把检索能力以 MCP 协议对外提供，任何 MCP 兼容客户端（Cursor / Claude Desktop /
LangGraph 等）都能接入。

运行：
    cd backend
    python -m app.mcp.server            # stdio 传输

工具：
    search_kb(query, top_k)   在企业知识库中检索相关段落
    get_citation(chunk_id)    按 chunk 取原文与出处（答案回查）

说明：本版本使用评测语料构建内存索引，便于零依赖复现；
接入真实数据时把 `_load_corpus()` 换成 `vector_store` 即可，工具契约不变。
"""
import sys
from pathlib import Path
from typing import Any

import numpy as np

_BACKEND_DIR = Path(__file__).resolve().parents[2]
if str(_BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(_BACKEND_DIR))

from mcp.server.mcpserver import MCPServer                            # noqa: E402

server = MCPServer(
    name="knowledgemind",
    version="0.1.0",
    instructions=(
        "企业知识检索服务。用于查询公司制度、流程、规定类问题。"
        "回答前先调用 search_kb 获取原文，再用 get_citation 回查出处；"
        "如果 search_kb 返回空或相关度低，应明确说明资料不足，不要编造。"
    ),
)

_state: dict[str, Any] = {}


def _load_corpus() -> list[dict]:
    """接入真实数据时替换这里（如从 vector_store 读 chunk）。"""
    from evaluation.sample_data import CORPUS

    return CORPUS


def _ensure_index() -> None:
    if _state:
        return
    from app.services.embedding import get_embedding

    embedding = get_embedding()
    corpus = _load_corpus()
    vectors = embedding.embed([item["content"] for item in corpus])
    _state["embedding"] = embedding
    _state["vectors"] = np.asarray(vectors, dtype=np.float32)
    _state["by_id"] = {item["chunk_id"]: item for item in corpus}


@server.tool()
def search_kb(query: str, top_k: int = 5) -> list[dict]:
    """在企业知识库中检索相关段落。

    当用户询问公司制度、流程、规定、政策类问题时使用。
    返回段落 id、所属文档、相关度与正文；相关度低于 0.35 通常意味着资料不足。

    Args:
        query: 用户问题原文，不要改写
        top_k: 返回条数，1-10，默认 5
    """
    _ensure_index()
    top_k = max(1, min(int(top_k or 5), 10))
    q = np.asarray(_state["embedding"].embed([query])[0], dtype=np.float32)
    matrix = _state["vectors"]
    sims = (matrix @ q) / (np.linalg.norm(matrix, axis=1) * np.linalg.norm(q) + 1e-9)
    order = np.argsort(-sims)[:top_k]
    corpus = _load_corpus()
    return [
        {
            "chunk_id": corpus[i]["chunk_id"],
            "title": corpus[i].get("title", ""),
            "document_id": corpus[i].get("doc_id", ""),
            "score": round(float(sims[i]), 4),
            "content": corpus[i]["content"],
        }
        for i in order
    ]


@server.tool()
def get_citation(chunk_id: str) -> dict:
    """按 chunk_id 取出原文与出处，用于回查答案依据。

    Args:
        chunk_id: search_kb 返回的段落 id
    """
    _ensure_index()
    item = _state["by_id"].get(chunk_id)
    if not item:
        return {"found": False, "chunk_id": chunk_id, "error": "未找到该段落"}
    return {
        "found": True,
        "chunk_id": chunk_id,
        "title": item.get("title", ""),
        "document_id": item.get("doc_id", ""),
        "content": item["content"],
    }


def main() -> None:
    import asyncio

    asyncio.run(server.run_stdio_async())


if __name__ == "__main__":
    main()
