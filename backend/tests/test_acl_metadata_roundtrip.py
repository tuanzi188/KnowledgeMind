"""文档 ACL 元数据往返测试。

覆盖此前的真实缺陷：ACL 列表写入向量库时被 str() 成 "['alice', 'bob']"，
读取时按逗号切分导致共享授权永远不生效。
"""
import json

import pytest

from app.core.user_context import UserContext
from app.models.chat import DocumentChunk
from app.services.access_control import (
    build_acl_metadata,
    can_access,
    filter_accessible_records,
    merge_acl_into_metadata,
)
from app.services.vector_store import VectorStore, _serialize_metadata_value


class _FakeEmbedding:
    def embed(self, texts):
        return [[0.1] * 512 for _ in texts]


class _FakeCollection:
    """只记录 metadata，不依赖 Chroma。"""

    def __init__(self):
        self.added = []

    def add(self, **kwargs):
        self.added.append(kwargs)

    def query(self, **kwargs):  # pragma: no cover - 本测试不做检索
        return {"ids": [[]], "documents": [[]], "metadatas": [[]], "distances": [[]]}


def _store_with_fake_collection():
    store = VectorStore()
    store._collection = _FakeCollection()
    store._ef = _FakeEmbedding()
    store._initialized = True
    return store


def test_acl_list_is_serialized_as_json():
    serialized = _serialize_metadata_value(["alice", "bob"])
    assert isinstance(serialized, str)
    assert json.loads(serialized) == ["alice", "bob"]
    # 标量保持原类型
    assert _serialize_metadata_value(True) is True
    assert _serialize_metadata_value(3) == 3


@pytest.mark.asyncio
async def test_shared_acl_survives_vector_store_roundtrip():
    store = _store_with_fake_collection()
    alice = UserContext(user_id="alice", roles=[])
    acl = build_acl_metadata(
        alice,
        allowed_users=["bob"],
        allowed_departments=["研发"],
        allowed_roles=["编辑"],
    )
    metadata = merge_acl_into_metadata(
        {"document_id": "doc-1", "title": "差旅制度"}, acl
    )
    chunk = DocumentChunk(
        chunk_id="chunk-1",
        doc_id="doc-1",
        content="一线城市住宿标准为每晚不超过 500 元。",
        metadata=metadata,
    )

    await store.add_chunks([chunk])
    stored = store._collection.added[0]["metadatas"][0]

    # 写入向量库后必须是 JSON 字符串，而不是 Python repr
    assert json.loads(stored["allowed_users"]) == ["bob"]
    assert json.loads(stored["allowed_departments"]) == ["研发"]
    assert json.loads(stored["allowed_roles"]) == ["编辑"]

    assert can_access(UserContext(user_id="bob"), stored) is True
    assert can_access(UserContext(user_id="dave", roles=["编辑"]), stored) is True
    assert can_access(UserContext(user_id="erin", department="研发"), stored) is True
    assert can_access(alice, stored) is True
    assert can_access(UserContext(user_id="carol", department="市场"), stored) is False


def test_legacy_python_repr_acl_is_still_readable():
    """兼容修复前写入的 "['bob', 'dave']" 这类历史数据。"""
    stored = {
        "owner": "alice",
        "is_public": False,
        "allowed_users": "['bob', 'dave']",
        "allowed_departments": "['研发']",
    }
    assert can_access(UserContext(user_id="bob"), stored) is True
    assert can_access(UserContext(user_id="dave"), stored) is True
    assert can_access(UserContext(user_id="carol", department="研发"), stored) is True
    assert can_access(UserContext(user_id="carol", department="市场"), stored) is False
    # CSV 形式仍兼容
    assert can_access(UserContext(user_id="bob"), {"allowed_users": "bob, carol"}) is True


def test_filter_accessible_records_after_serialization():
    stored = {
        "owner": "alice",
        "is_public": False,
        "allowed_users": json.dumps(["bob"], ensure_ascii=False),
    }
    records = [{"chunk_id": "c1", "metadata": stored}]

    assert len(filter_accessible_records(UserContext(user_id="bob"), records)) == 1
    assert len(filter_accessible_records(UserContext(user_id="carol"), records)) == 0
    assert len(filter_accessible_records(UserContext(user_id="root", roles=["admin"]), records)) == 1
