"""托管重排客户端的最小单元测试：只验报文兼容与降级约定，不打网络。"""
from app.services import rerank_api


def test_extract_results_cohere_shape():
    payload = {"results": [{"index": 0, "relevance_score": 0.9}]}
    assert rerank_api._extract_results(payload) == payload["results"]


def test_extract_results_dashscope_shape():
    payload = {"output": {"results": [{"index": 1, "relevance_score": 0.4}]}}
    assert rerank_api._extract_results(payload) == payload["output"]["results"]


def test_extract_results_tolerates_garbage():
    assert rerank_api._extract_results(None) == []
    assert rerank_api._extract_results({"results": "oops"}) == []
    assert rerank_api._extract_results({"results": []}) == []


def test_describe_reports_current_mode():
    described = rerank_api.describe()
    assert described["mode"] in {"remote", "local"}
    assert described["status"] in {"healthy", "degraded"}
    assert described.get("model")


async def test_remote_rerank_returns_none_without_key(monkeypatch):
    monkeypatch.setitem(rerank_api.RERANK_CONFIG, "api_key", "")
    assert await rerank_api.remote_rerank("年假怎么申请", ["年假 5 天"], 1) is None


async def test_remote_rerank_returns_none_for_empty_documents():
    assert await rerank_api.remote_rerank("q", [], 1) is None
