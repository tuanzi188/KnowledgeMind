import asyncio
from uuid import uuid4

import pytest

from app.core.conversation_scope import ConversationNamespace
from app.core.user_context import UserContext
from app.services.conversation_memory import ConversationMemory, JsonSessionStore


@pytest.mark.asyncio
async def test_scoped_sessions_survive_reload(tmp_path):
    session_store = JsonSessionStore(str(tmp_path))
    first_memory = ConversationMemory(store=session_store)
    first_namespace = ConversationNamespace(UserContext(user_id="alice"))
    public_identifier = str(uuid4())
    private_identifier = first_namespace.storage_id(public_identifier)
    await first_memory.add_turn(private_identifier, "问题", "回答")
    await first_memory.flush()
    first_memory._flush_task.cancel()
    second_memory = ConversationMemory(store=JsonSessionStore(str(tmp_path)))
    await second_memory._init_store()
    reloaded_session = await second_memory.get_conversation(private_identifier)
    assert reloaded_session["turns"][0]["answer"] == "回答"
    assert first_namespace.public_id(reloaded_session["conversation_id"]) == public_identifier
    assert ConversationNamespace(UserContext(user_id="bob")).public_id(private_identifier) is None


@pytest.mark.asyncio
async def test_session_limit_does_not_deadlock(tmp_path):
    bounded_memory = ConversationMemory(max_sessions=1, store=JsonSessionStore(str(tmp_path)))
    await bounded_memory.get_or_create_session(str(uuid4()))
    next_session_id = str(uuid4())
    new_session = await asyncio.wait_for(bounded_memory.get_or_create_session(next_session_id), timeout=1)
    assert new_session.conversation_id == next_session_id
    assert len(bounded_memory._sessions) == 1
