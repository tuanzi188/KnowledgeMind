import logging
from typing import Any, Dict, List

from app.core.user_context import UserContext

logger = logging.getLogger(__name__)

ACL_METADATA_KEYS = {
    "owner",
    "allowed_users",
    "allowed_departments",
    "allowed_roles",
    "is_public",
}


def _normalize_list(value: Any) -> List[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return [item.strip() for item in value.split(",") if item.strip()]
    if isinstance(value, (list, tuple)):
        return [str(item).strip() for item in value if str(item).strip()]
    return [str(value).strip()] if str(value).strip() else []


def can_access(user_context: UserContext, metadata: Dict[str, Any]) -> bool:
    """判断用户是否有权读取该文档/chunk。"""
    if user_context.is_admin:
        return True

    metadata = metadata or {}

    if metadata.get("is_public") is True:
        return True

    owner = str(metadata.get("owner", "")).strip()
    if owner and owner == user_context.user_id:
        return True

    if user_context.user_id:
        allowed_users = _normalize_list(metadata.get("allowed_users"))
        if user_context.user_id in allowed_users:
            return True

    if user_context.department:
        allowed_departments = _normalize_list(metadata.get("allowed_departments"))
        if user_context.department in allowed_departments:
            return True

    if user_context.roles:
        allowed_roles = _normalize_list(metadata.get("allowed_roles"))
        allowed_roles = [r.lower() for r in allowed_roles]
        if any(role.lower() in allowed_roles for role in user_context.roles):
            return True

    return False


def can_manage(user_context: UserContext, metadata: Dict[str, Any]) -> bool:
    """判断用户是否有权修改/删除该文档。

    管理员或文档 owner 可管理；其他角色即使可读也不可删除。
    """
    if user_context.is_admin:
        return True

    metadata = metadata or {}
    owner = str(metadata.get("owner", "")).strip()
    if owner and owner == user_context.user_id:
        return True

    return False


def filter_accessible_records(
    user_context: UserContext,
    records: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """过滤用户有权限访问的记录列表。"""
    if user_context.is_admin:
        return records

    accessible = []
    for record in records:
        metadata = record.get("metadata", {}) or {}
        if can_access(user_context, metadata):
            accessible.append(record)
    return accessible


def build_acl_metadata(
    user_context: UserContext,
    allowed_users: List[str] = None,
    allowed_departments: List[str] = None,
    allowed_roles: List[str] = None,
    is_public: bool = False,
) -> Dict[str, Any]:
    """为上传的文档构建 ACL 元数据。"""
    acl = {
        "owner": user_context.user_id,
        "is_public": is_public,
    }
    if allowed_users:
        acl["allowed_users"] = _normalize_list(allowed_users)
    if allowed_departments:
        acl["allowed_departments"] = _normalize_list(allowed_departments)
    if allowed_roles:
        acl["allowed_roles"] = [r.lower() for r in _normalize_list(allowed_roles)]
    return acl


def merge_acl_into_metadata(
    metadata: Dict[str, Any],
    acl: Dict[str, Any],
) -> Dict[str, Any]:
    """将 ACL 字段合并到文档 metadata 中。"""
    merged = dict(metadata)
    for key in ACL_METADATA_KEYS:
        if key in acl:
            merged[key] = acl[key]
    return merged
