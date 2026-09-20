import secrets
import logging
import os
from typing import Optional
from fastapi import Depends, HTTPException, status, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

from app.config import API_KEY
from app.core.identity_keys import parse_identity_keys
from app.core.user_context import extract_user_context, UserContext
from app.services.audit_logger import audit_logger, AuditAction, AuditStatus, AuditEvent

logger = logging.getLogger(__name__)

security_scheme = HTTPBearer(auto_error=False)

API_KEY_HEADER = "X-API-Key"
API_IDENTITIES = parse_identity_keys(os.getenv("AUTH_USERS_JSON", ""))


async def verify_api_key(
    request: Request,
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security_scheme),
) -> UserContext:
    user_context = extract_user_context(request)

    if not API_KEY and not API_IDENTITIES:
        request.state.authenticated_user = user_context
        return user_context

    provided_key = None
    if credentials is not None:
        provided_key = credentials.credentials

    if not provided_key:
        provided_key = request.headers.get(API_KEY_HEADER)

    async def _log_auth(auth_status: AuditStatus, error_message: str = ""):
        await audit_logger.log(
            AuditEvent(
                user_context=user_context,
                action=AuditAction.AUTH_FAILURE if auth_status == AuditStatus.FAILURE else AuditAction.AUTH_SUCCESS,
                resource_type="auth",
                status=auth_status,
                details={"auth_method": "api_key"},
                error_message=error_message,
            )
        )

    if not provided_key:
        await _log_auth(AuditStatus.FAILURE, "Missing API key")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing API key. Provide it via Authorization: Bearer <key> or X-API-Key header",
            headers={"WWW-Authenticate": "Bearer"},
        )

    matched_identity = next((
        identity for identity in API_IDENTITIES
        if secrets.compare_digest(provided_key.encode("utf-8"), identity["token"].encode("utf-8"))
    ), None)
    shared_key_valid = (
        not API_IDENTITIES and API_KEY
        and secrets.compare_digest(provided_key.encode("utf-8"), API_KEY.encode("utf-8"))
    )
    if matched_identity is None and not shared_key_valid:
        await _log_auth(AuditStatus.FAILURE, "Invalid API key")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid API key",
        )

    if matched_identity is not None:
        user_context = UserContext(
            user_id=matched_identity["user_id"],
            roles=list(matched_identity["roles"]),
            department=matched_identity["department"],
            ip_address=user_context.ip_address,
            user_agent=user_context.user_agent,
        )
    request.state.authenticated_user = user_context
    await _log_auth(AuditStatus.SUCCESS)
    return user_context


async def require_administrator(
    verified_user: UserContext = Depends(verify_api_key),
) -> UserContext:
    if not verified_user.is_admin:
        raise HTTPException(status_code=403, detail="需要管理员权限")
    return verified_user
