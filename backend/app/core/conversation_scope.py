from hashlib import sha256
from typing import Optional
from uuid import UUID

from fastapi import HTTPException

from app.core.user_context import UserContext


class ConversationNamespace:
    """使用可信身份隔离存储键，对外仍使用 UUID 会话编号。"""

    def __init__(self, user_context: UserContext):
        self.prefix = (
            "" if user_context.user_id == "anonymous"
            else sha256(user_context.user_id.encode("utf-8")).hexdigest() + "_"
        )

    def storage_id(self, public_id: str) -> str:
        try:
            canonical_id = str(UUID(public_id))
        except (ValueError, TypeError, AttributeError) as exc:
            raise HTTPException(status_code=422, detail="会话编号必须是 UUID") from exc
        return self.prefix + canonical_id

    def public_id(self, stored_id: str) -> Optional[str]:
        if not stored_id.startswith(self.prefix):
            return None
        candidate_id = stored_id[len(self.prefix):]
        try:
            return str(UUID(candidate_id))
        except (ValueError, TypeError, AttributeError):
            return None
