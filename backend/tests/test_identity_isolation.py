import json
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from fastapi import Depends, FastAPI
from httpx import ASGITransport, AsyncClient

from app.api import chat as chat_api
from app.api import analytics as analytics_api
from app.core import auth
from app.core.conversation_scope import ConversationNamespace
from app.core.identity_keys import parse_identity_keys
from app.core.user_context import UserContext
from app.models.chat import ChatResponse
from app.services.conversation_memory import ConversationMemory, JsonSessionStore


@pytest.fixture
def identity_app(monkeypatch, tmp_path):
    test_identities = [
        {"token": "a" * 32, "user_id": "alice", "roles": ["user"], "department": "研发"},
        {"token": "b" * 32, "user_id": "bob", "roles": ["user"], "department": "销售"},
    ]
    monkeypatch.setattr(auth, "API_IDENTITIES", test_identities)
    monkeypatch.setattr(auth, "API_KEY", "legacy-shared-key")
    monkeypatch.setattr(auth.audit_logger, "log", AsyncMock())
    isolated_memory = ConversationMemory(store=JsonSessionStore(str(tmp_path)))
    monkeypatch.setattr(chat_api, "conversation_memory", isolated_memory)

    async def isolated_rag(**request_options):
        stored_key = request_options["conversation_id"]
        session_record = await isolated_memory.get_or_create_session(stored_key)
        session_record.add_turn(request_options["query"], "测试回答")
        return ChatResponse(answer="测试回答", conversation_id=stored_key)

    async def isolated_stream(**request_options):
        await isolated_rag(**request_options)
        yield "测试回答"

    monkeypatch.setattr(chat_api, "rag_query", isolated_rag)
    monkeypatch.setattr(chat_api, "rag_query_stream", isolated_stream)
    test_application = FastAPI()
    test_application.include_router(chat_api.router, dependencies=[Depends(auth.verify_api_key)])
    test_application.include_router(analytics_api.router, dependencies=[Depends(auth.verify_api_key)])
    return test_application, isolated_memory


@pytest.mark.asyncio
async def test_forged_roles_are_ignored(identity_app):
    application, _ = identity_app
    async with AsyncClient(transport=ASGITransport(app=application), base_url="http://test") as client:
        forged_response = await client.get("/auth/me", headers={
            "Authorization": "Bearer " + "a" * 32,
            "X-User-ID": "bob",
            "X-User-Roles": "admin",
            "X-User-Department": "finance",
        })
        assert forged_response.status_code == 200
        assert forged_response.json() == {"userId": "alice", "roles": ["user"], "department": "研发"}
        denied_response = await client.get("/analytics/overview", headers={
            "Authorization": "Bearer " + "a" * 32, "X-User-Roles": "admin",
        })
        assert denied_response.status_code == 403


@pytest.mark.asyncio
async def test_auth_rejects_missing_invalid_and_shared_keys(identity_app):
    application, _ = identity_app
    async with AsyncClient(transport=ASGITransport(app=application), base_url="http://test") as client:
        assert (await client.get("/auth/me")).status_code == 401
        for rejected_key in ["wrong", "legacy-shared-key"]:
            response = await client.get("/auth/me", headers={"X-API-Key": rejected_key})
            assert response.status_code == 403


@pytest.mark.asyncio
async def test_conversation_endpoints_are_isolated(identity_app):
    application, memory = identity_app
    alice_headers = {"Authorization": "Bearer " + "a" * 32}
    bob_headers = {"Authorization": "Bearer " + "b" * 32}
    public_conversation_id = str(uuid4())
    async with AsyncClient(transport=ASGITransport(app=application), base_url="http://test") as client:
        created_response = await client.post("/chat", headers=alice_headers, json={
            "query": "甲的私有问题", "conversation_id": public_conversation_id,
        })
        assert created_response.status_code == 200
        assert created_response.json()["conversation_id"] == public_conversation_id
        assert len((await client.get("/conversations", headers=alice_headers)).json()["conversations"]) == 1
        assert (await client.get("/conversations", headers=bob_headers)).json()["conversations"] == []
        for request_method in ["GET", "DELETE"]:
            forbidden_response = await client.request(
                request_method, "/conversations/" + public_conversation_id, headers=bob_headers,
            )
            assert forbidden_response.status_code == 404
        stream_response = await client.post("/chat/stream", headers=bob_headers, json={
            "query": "乙的私有问题", "conversation_id": public_conversation_id,
        })
        assert stream_response.status_code == 200
        stream_events = [json.loads(line[6:]) for line in stream_response.text.splitlines() if line.startswith("data: ")]
        assert stream_events[-1]["conversation_id"] == public_conversation_id
        for headers, expected_query in [(alice_headers, "甲的私有问题"), (bob_headers, "乙的私有问题")]:
            detail_response = await client.get("/conversations/" + public_conversation_id, headers=headers)
            assert detail_response.json()["turns"][0]["query"] == expected_query
        assert len(memory._sessions) == 2
        assert (await client.delete("/conversations/" + public_conversation_id, headers=bob_headers)).status_code == 200
        assert (await client.get("/conversations/" + public_conversation_id, headers=alice_headers)).status_code == 200


@pytest.mark.asyncio
async def test_invalid_session_id_never_reaches_storage(identity_app):
    application, memory = identity_app
    async with AsyncClient(transport=ASGITransport(app=application), base_url="http://test") as client:
        invalid_response = await client.post("/chat", headers={"X-API-Key": "a" * 32}, json={
            "query": "测试", "conversation_id": "../../outside",
        })
        assert invalid_response.status_code == 422
        assert not memory._sessions


def test_identity_configuration_fails_closed():
    for invalid_configuration in [
        "{", "{}", "[]", '[{"token":"short","user_id":"alice"}]',
        json.dumps([{"token": "a" * 32, "user_id": " anonymous "}]),
    ]:
        with pytest.raises(ValueError):
            parse_identity_keys(invalid_configuration)
    configured_identity = {"token": "a" * 32, "user_id": "alice", "roles": ["ADMIN"]}
    assert parse_identity_keys(json.dumps([configured_identity]))[0]["roles"] == ["admin"]
    with pytest.raises(ValueError):
        parse_identity_keys(json.dumps([configured_identity, configured_identity]))


def test_legacy_sessions_are_only_visible_in_single_user_mode():
    legacy_public_id = str(uuid4())
    legacy_namespace = ConversationNamespace(UserContext())
    alice_namespace = ConversationNamespace(UserContext(user_id="alice"))
    assert legacy_namespace.public_id(legacy_public_id) == legacy_public_id
    assert alice_namespace.public_id(legacy_public_id) is None
    assert legacy_namespace.public_id(alice_namespace.storage_id(legacy_public_id)) is None
