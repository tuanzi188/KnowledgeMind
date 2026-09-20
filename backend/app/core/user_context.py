from dataclasses import dataclass
from typing import List
from fastapi import Request


@dataclass
class UserContext:
    """经过服务端认证的用户上下文。"""

    user_id: str = "anonymous"
    roles: List[str] = None
    department: str = ""
    ip_address: str = ""
    user_agent: str = ""

    def __post_init__(self):
        if self.roles is None:
            self.roles = []

    @property
    def is_admin(self) -> bool:
        return "admin" in self.roles

    @property
    def display_name(self) -> str:
        return self.user_id


def extract_user_context(request: Request) -> UserContext:
    """只读取认证依赖保存的身份，不相信客户端提交的角色或用户 ID。"""
    verified_identity = getattr(request.state, "authenticated_user", None)
    if isinstance(verified_identity, UserContext):
        return verified_identity
    return UserContext(
        ip_address=request.client.host if request.client else "",
        user_agent=request.headers.get("User-Agent", ""),
    )
