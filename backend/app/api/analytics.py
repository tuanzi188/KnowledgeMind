import logging
import asyncio

from fastapi import APIRouter, Depends, HTTPException, Request

from app.models.analytics import (
    AnalyticsResponse,
    AuditLogQueryRequest,
    AuditLogQueryResponse,
    DocumentAnalyticsRequest,
    ConversationAnalyticsRequest,
    TaskAnalyticsRequest,
    GraphAnalyticsRequest,
)
from app.core.user_context import extract_user_context
from app.core.auth import require_administrator
from app.core.exceptions import UpstreamAPIError
from app.services.analytics import analytics_service
from app.services.conversation_memory import conversation_memory
from app.services.graph_search import graph_searcher
from app.services.task_queue import task_queue
from app.services.vector_store import vector_store
from app.services.audit_logger import audit_logger, AuditAction, AuditStatus, AuditEvent

logger = logging.getLogger(__name__)
router = APIRouter(dependencies=[Depends(require_administrator)])


def _handle_endpoint_error(operation: str, exc: Exception) -> None:
    if isinstance(exc, UpstreamAPIError):
        logger.warning(
            "%s upstream error [%s]: %s",
            operation,
            exc.status_code,
            exc.detail,
        )
        raise HTTPException(status_code=exc.status_code, detail=exc.detail) from exc
    logger.error("%s error: %s", operation, exc, exc_info=True)
    raise HTTPException(status_code=500, detail="Internal server error") from exc


async def _log_analytics_access(request: Request, action: AuditAction, details: dict = None):
    user_context = extract_user_context(request)
    await audit_logger.log(
        AuditEvent(
            user_context=user_context,
            action=action,
            resource_type="analytics",
            status=AuditStatus.SUCCESS,
            details=details or {},
        )
    )


async def _list_all_chunks() -> list[dict]:
    """流式读取所有 chunks，避免一次性全量加载。"""
    chunks: list[dict] = []
    async for chunk in vector_store.list_chunks_stream(page_size=1000):
        chunks.append(chunk)
    return chunks


async def _list_all_tasks() -> list[dict]:
    """列出所有内存中的任务（含已完成/失败）。"""
    return await task_queue.list_tasks(status=None, limit=10000)


@router.get("/analytics/overview", response_model=AnalyticsResponse)
async def get_analytics_overview(request: Request):
    """系统运行总览数据分析。"""
    try:
        chunks = await _list_all_chunks()
        conversations = await conversation_memory.list_conversations()
        tasks = await _list_all_tasks()
        result = await analytics_service.get_overview(
            chunks=chunks,
            conversations=conversations,
            tasks=tasks,
            graph_searcher=graph_searcher,
        )
        await _log_analytics_access(request, AuditAction.ANALYTICS_VIEW, {"metric": "overview"})
        return AnalyticsResponse(**result)
    except HTTPException:
        raise
    except Exception as e:
        _handle_endpoint_error("Analytics overview", e)


@router.post("/analytics/documents", response_model=AnalyticsResponse)
async def analyze_documents(request: Request, body: DocumentAnalyticsRequest):
    """文档与 chunks 数据分析。"""
    try:
        chunks = await _list_all_chunks()
        result = await analytics_service.analyze_documents(
            chunks=chunks,
            request=body.model_dump(exclude_none=True),
        )
        await _log_analytics_access(request, AuditAction.ANALYTICS_VIEW, {"metric": "documents"})
        return AnalyticsResponse(**result)
    except HTTPException:
        raise
    except Exception as e:
        _handle_endpoint_error("Document analytics", e)


@router.post("/analytics/conversations", response_model=AnalyticsResponse)
async def analyze_conversations(request: Request, body: ConversationAnalyticsRequest):
    """对话数据分析。"""
    try:
        conversations = await conversation_memory.list_conversations()
        result = await analytics_service.analyze_conversations(
            conversations=conversations,
            request=body.model_dump(exclude_none=True),
        )
        await _log_analytics_access(request, AuditAction.ANALYTICS_VIEW, {"metric": "conversations"})
        return AnalyticsResponse(**result)
    except HTTPException:
        raise
    except Exception as e:
        _handle_endpoint_error("Conversation analytics", e)


@router.post("/analytics/tasks", response_model=AnalyticsResponse)
async def analyze_tasks(request: Request, body: TaskAnalyticsRequest):
    """任务队列数据分析。"""
    try:
        tasks = await _list_all_tasks()
        result = await analytics_service.analyze_tasks(
            tasks=tasks,
            request=body.model_dump(exclude_none=True),
        )
        await _log_analytics_access(request, AuditAction.ANALYTICS_VIEW, {"metric": "tasks"})
        return AnalyticsResponse(**result)
    except HTTPException:
        raise
    except Exception as e:
        _handle_endpoint_error("Task analytics", e)


@router.post("/analytics/graph", response_model=AnalyticsResponse)
async def analyze_graph(request: Request, body: GraphAnalyticsRequest):
    """知识图谱数据分析。"""
    try:
        result = await analytics_service.analyze_graph(
            graph_searcher=graph_searcher,
            request=body.model_dump(exclude_none=True),
        )
        await _log_analytics_access(request, AuditAction.ANALYTICS_VIEW, {"metric": "graph"})
        return AnalyticsResponse(**result)
    except HTTPException:
        raise
    except Exception as e:
        _handle_endpoint_error("Graph analytics", e)


@router.post("/analytics/audit", response_model=AuditLogQueryResponse)
async def query_audit_logs(request: Request, body: AuditLogQueryRequest):
    """审计日志查询（建议仅管理员使用）。"""
    user_context = extract_user_context(request)
    if not user_context.is_admin:
        raise HTTPException(status_code=403, detail="Admin access required")

    logs = await audit_logger.query(
        user_id=body.user_id,
        action=body.action,
        resource_type=body.resource_type,
        resource_id=body.resource_id,
        status=body.status,
        start_time=body.start_time,
        end_time=body.end_time,
        limit=body.limit,
        offset=body.offset,
    )
    await _log_analytics_access(request, AuditAction.ANALYTICS_VIEW, {"metric": "audit", "result_count": len(logs)})
    return AuditLogQueryResponse(total=len(logs), logs=logs)
