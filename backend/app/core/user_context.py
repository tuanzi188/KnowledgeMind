from dataclasses import dataclass
from typing import List
from fastapi import Request


@dataclass
class UserContext:
    """从请求头解析的用户上下文。"""

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
    """从请求头提取用户身份信息。

    兼容现有 API Key 模式：未提供用户头时回退到 anonymous。
    """
    user_id = request.headers.get("X-User-ID", "anonymous").strip() or "anonymous"
    roles_header = request.headers.get("X-User-Roles", "")
    department = request.headers.get("X-User-Department", "").strip()

    roles = []
    if roles_header:
        for role in roles_header.split(","):
            role = role.strip().lower()
            if role:
                roles.append(role)

    client_ip = request.client.host if request.client else ""
    forwarded_for = request.headers.get("X-Forwarded-For", "")
    if forwarded_for:
        client_ip = forwarded_for.split(",")[0].strip()

    return UserContext(
        user_id=user_id,
        roles=roles,
        department=department,
        ip_address=client_ip,
        user_agent=request.headers.get("User-Agent", ""),
    )
