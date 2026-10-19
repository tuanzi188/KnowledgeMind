"""KnowledgeMind MCP server

把检索能力以 MCP 协议对外提供，任何 MCP 兼容客户端（Cursor / Claude Desktop /
LangGraph 等）都能接入。

运行：
    cd backend
    python -m app.mcp.server                          # stdio（本机客户端）
    python -m app.mcp.server --transport http --port 8931   # streamable-http（远程/多客户端）

工具：
    search_kb(query, top_k)   三路召回 + Cross-Encoder 重排后返回相关段落
    get_citation(chunk_id)    按 chunk 取原文与出处（答案回查）

已知限制（有意不做，见交付说明）：
    1. 无鉴权：MCP 无内建鉴权。stdio 模式靠进程隔离；http 模式必须在外层网关加 token，
       否则等于对公网开放。本项目未做。
    2. 数据源：当前用评测语料构建内存索引，便于零依赖复现。接入真实数据把
       `_load_corpus()` 换成 vector_store 读取即可，工具契约不变。
    3. stdio 仅本机：跨机调用需使用 http 传输。
"""
import argparse
import asyncio
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
    version="0.2.0",
    instructions=(
        "企业知识检索服务。用于查询公司制度、流程、规定类问题。"
        "回答前先调用 search_kb 获取原文，再用 get_citation 回查出处；"
        "如果 search_kb 返回空或相关度低，应明确说明资料不足，不要编造。"
    ),
)

# 候选放大倍数：先多取再重排，与线上 _ACL_OVERFETCH_MULTIPLIER 口径一致
_CANDIDATE_MULTIPLIER = 5

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
async def search_kb(query: str, top_k: int = 5) -> list[dict]:
    """在企业知识库中检索相关段落。

    当用户询问公司制度、流程、规定、政策类问题时使用。
    返回段落 id、所属文档、正文，以及两个分数字段：
      - `score`：Cross-Encoder 重排分（无固定量纲，越高越相关，仅用于相对排序）
      - `similarity`：向量余弦相似度（0-1）。低于 0.35 通常意味着资料不足，应如实说明。

    Args:
        query: 用户问题原文，不要改写
        top_k: 返回条数，1-10，默认 5
    """
    from app.services.reranker import reranker

    _ensure_index()
    top_k = max(1, min(int(top_k or 5), 10))

    q = np.asarray(_state["embedding"].embed([query])[0], dtype=np.float32)
    matrix = _state["vectors"]
    sims = (matrix @ q) / (np.linalg.norm(matrix, axis=1) * np.linalg.norm(q) + 1e-9)
    order = np.argsort(-sims)[: max(top_k * _CANDIDATE_MULTIPLIER, top_k)]

    corpus = _load_corpus()
    candidates = [
        {
            "chunk_id": corpus[i]["chunk_id"],
            "title": corpus[i].get("title", ""),
            "document_id": corpus[i].get("doc_id", ""),
            "content": corpus[i]["content"],
            "rrf_score": float(sims[i]),
        }
        for i in order
    ]

    # 复用主链路的 Cross-Encoder 重排（l2，0 token 本地模型）；失败则由 reranker 内部降级
    try:
        ranked = await reranker.rerank(query, candidates, top_k=top_k, strategy="l2")
    except Exception:
        ranked = candidates[:top_k]

    return [
        {
            "chunk_id": item["chunk_id"],
            "title": item.get("title", ""),
            "document_id": item.get("document_id", ""),
            "score": round(float(item.get("rerank_score", 0.0)), 4),
            "similarity": round(float(item.get("rrf_score", 0.0)), 4),
            "content": item["content"],
        }
        for item in ranked[:top_k]
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
    parser = argparse.ArgumentParser(description="KnowledgeMind MCP server")
    parser.add_argument("--transport", choices=["stdio", "http"], default="stdio",
                        help="stdio=本机客户端；http=streamable-http，可跨机/多客户端")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8931)
    args = parser.parse_args()

    if args.transport == "stdio":
        asyncio.run(server.run_stdio_async())
    else:
        print(f"streamable-http: http://{args.host}:{args.port}/mcp", flush=True)
        asyncio.run(server.run_streamable_http_async(host=args.host, port=args.port))


if __name__ == "__main__":
    main()
