import secrets
import logging
import asyncio
from typing import Optional
from fastapi import Depends, HTTPException, status, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

from app.config import API_KEY
from app.core.user_context import extract_user_context, UserContext
from app.services.audit_logger import audit_logger, AuditAction, AuditStatus, AuditEvent

logger = logging.getLogger(__name__)

security_scheme = HTTPBearer(auto_error=False)

API_KEY_HEADER = "X-API-Key"


async def verify_api_key(
    request: Request,
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security_scheme),
) -> UserContext:
    user_context = extract_user_context(request)

    if not API_KEY:
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

    if not secrets.compare_digest(provided_key, API_KEY):
        await _log_auth(AuditStatus.FAILURE, "Invalid API key")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid API key",
        )

    await _log_auth(AuditStatus.SUCCESS)
    return user_context