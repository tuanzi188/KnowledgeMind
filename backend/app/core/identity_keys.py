import json
from typing import Any, Dict, List


def parse_identity_keys(raw_config: str) -> List[Dict[str, Any]]:
    """验证服务端身份配置，配置错误时拒绝启动而不是放开认证。"""
    if not raw_config.strip():
        return []
    try:
        configured_identities = json.loads(raw_config)
    except json.JSONDecodeError as exc:
        raise ValueError("AUTH_USERS_JSON 必须是有效的 JSON 数组") from exc
    if not isinstance(configured_identities, list) or not configured_identities:
        raise ValueError("AUTH_USERS_JSON 必须是非空身份数组")
    validated_identities = []
    identity_tokens = set()
    for identity_entry in configured_identities:
        if not isinstance(identity_entry, dict):
            raise ValueError("身份配置必须是对象")
        identity_token = identity_entry.get("token", "")
        identity_name = identity_entry.get("user_id", "")
        identity_roles = identity_entry.get("roles", [])
        identity_department = identity_entry.get("department", "")
        if not isinstance(identity_token, str) or len(identity_token) < 24:
            raise ValueError("用户访问令牌至少需要 24 个字符")
        if not identity_token.isascii() or identity_token.strip() != identity_token:
            raise ValueError("用户访问令牌必须是不含首尾空白的 ASCII 字符串")
        if identity_token in identity_tokens:
            raise ValueError("用户访问令牌不能重复")
        if not isinstance(identity_name, str) or not identity_name.strip() or identity_name.strip() == "anonymous":
            raise ValueError("用户 ID 必须非空，且不能使用保留名称 anonymous")
        if not isinstance(identity_roles, list) or any(not isinstance(role, str) for role in identity_roles):
            raise ValueError("roles 必须是字符串数组")
        if not isinstance(identity_department, str):
            raise ValueError("department 必须是字符串")
        identity_tokens.add(identity_token)
        validated_identities.append({
            "token": identity_token,
            "user_id": identity_name.strip(),
            "roles": [role.strip().lower() for role in identity_roles if role.strip()],
            "department": identity_department.strip(),
        })
    return validated_identities
