"""MCP 客户端示例：证明检索服务可被任意 MCP 兼容客户端调用。

用法：
    cd backend
    python -m app.mcp.demo_client                          # stdio：起子进程做服务端
    python -m app.mcp.demo_client --url http://127.0.0.1:8931/mcp   # 连已启动的 http 服务

    # 另开一个终端先起服务：
    # python -m app.mcp.server --transport http --port 8931

输出：握手信息 → 工具清单 → 一次检索调用 → 一次出处回查。

注意：MCP v2 会把返回列表拆成多个 content block（每块一个 JSON），
不要只读 content[0] —— 这是接入时最容易踩的坑。
"""
import argparse
import asyncio
import json
import sys
from pathlib import Path

_BACKEND_DIR = Path(__file__).resolve().parents[2]
if str(_BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(_BACKEND_DIR))

from mcp import Client, StdioServerParameters                             # noqa: E402


async def main() -> None:
    parser = argparse.ArgumentParser(description="KnowledgeMind MCP 客户端示例")
    parser.add_argument("--url", default="", help="已启动的 streamable-http 服务地址；留空则用 stdio")
    args = parser.parse_args()

    if args.url:
        target = args.url
    else:
        target = StdioServerParameters(
            command=sys.executable,
            args=["-m", "app.mcp.server"],
            cwd=str(_BACKEND_DIR),
        )

    async with Client(target) as client:
        info = client.server_info
        print(f"握手成功：{info.name} v{info.version}，协议 {client.protocol_version}")

        tools = getattr(await client.list_tools(), "tools", [])
        print(f"工具 {len(tools)} 个：")
        for tool in tools:
            params_desc = list(((getattr(tool, "input_schema", None) or {}).get("properties") or {}).keys())
            print(f"  - {tool.name}({', '.join(params_desc)})")

        result = await client.call_tool("search_kb", {"query": "试用期是多久", "top_k": 3})
        hits = [json.loads(block.text) for block in result.content]
        print(f"\n检索命中 {len(hits)} 条：")
        for hit in hits:
            print(f"  {hit['chunk_id']} | {hit['title']} | score={hit['score']} | {hit['content'][:34]}")

        if hits:
            cite = json.loads((await client.call_tool("get_citation", {"chunk_id": hits[0]["chunk_id"]})).content[0].text)
            print(f"\n出处回查：found={cite['found']} 文档={cite['title']}")
            print(f"  原文：{cite['content'][:60]}")


if __name__ == "__main__":
    asyncio.run(main())
