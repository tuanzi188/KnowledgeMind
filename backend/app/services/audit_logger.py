import asyncio
import json
import logging
import os
import time
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional

from app.config import DATA_DIR
from app.core.user_context import UserContext

logger = logging.getLogger(__name__)

DEFAULT_AUDIT_DIR = DATA_DIR / "audit_logs"
DEFAULT_AUDIT_DIR.mkdir(parents=True, exist_ok=True)

AUDIT_BUFFER_SIZE = int(os.getenv("AUDIT_BUFFER_SIZE", "100"))
AUDIT_FLUSH_INTERVAL_SECONDS = float(os.getenv("AUDIT_FLUSH_INTERVAL_SECONDS", "5"))
AUDIT_RETENTION_DAYS = int(os.getenv("AUDIT_RETENTION_DAYS", "90"))


class AuditAction(str, Enum):
    DOCUMENT_UPLOAD = "document_upload"
    DOCUMENT_DELETE = "document_delete"
    DOCUMENT_LIST = "document_list"
    DOCUMENT_SEARCH = "document_search"
    CHAT_QUERY = "chat_query"
    CHAT_STREAM = "chat_stream"
    CONVERSATION_LIST = "conversation_list"
    CONVERSATION_VIEW = "conversation_view"
    CONVERSATION_DELETE = "conversation_delete"
    TASK_VIEW = "task_view"
    ANALYTICS_VIEW = "analytics_view"
    AUTH_SUCCESS = "auth_success"
    AUTH_FAILURE = "auth_failure"


class AuditStatus(str, Enum):
    SUCCESS = "success"
    FAILURE = "failure"
    DENIED = "denied"


class AuditEvent:
    __slots__ = (
        "timestamp", "user_id", "roles", "department", "ip_address", "user_agent",
        "action", "resource_type", "resource_id", "status", "duration_ms",
        "details", "error_message",
    )

    def __init__(
        self,
        user_context: UserContext,
        action: AuditAction,
        resource_type: str = "",
        resource_id: str = "",
        status: AuditStatus = AuditStatus.SUCCESS,
        duration_ms: float = 0.0,
        details: Optional[Dict[str, Any]] = None,
        error_message: str = "",
    ):
        self.timestamp = datetime.now().isoformat()
        self.user_id = user_context.user_id
        self.roles = user_context.roles
        self.department = user_context.department
        self.ip_address = user_context.ip_address
        self.user_agent = user_context.user_agent
        self.action = action.value
        self.resource_type = resource_type
        self.resource_id = str(resource_id) if resource_id else ""
        self.status = status.value
        self.duration_ms = round(duration_ms, 2)
        self.details = details or {}
        self.error_message = error_message

    def to_dict(self) -> Dict[str, Any]:
        return {
            "timestamp": self.timestamp,
            "user_id": self.user_id,
            "roles": self.roles,
            "department": self.department,
            "ip_address": self.ip_address,
            "user_agent": self.user_agent,
            "action": self.action,
            "resource_type": self.resource_type,
            "resource_id": self.resource_id,
            "status": self.status,
            "duration_ms": self.duration_ms,
            "details": self.details,
            "error_message": self.error_message,
        }


class AuditLogger:
    """异步审计日志服务。

    特性：
    - 内存缓冲 + 阈值/定时刷盘，减少 IO 开销
    - 按天轮转 JSONL 文件
    - 自动清理过期日志
    - 未 flush 的数据在应用关闭时尽力持久化
    """

    def __init__(
        self,
        log_dir: Path = DEFAULT_AUDIT_DIR,
        buffer_size: int = AUDIT_BUFFER_SIZE,
        flush_interval: float = AUDIT_FLUSH_INTERVAL_SECONDS,
        retention_days: int = AUDIT_RETENTION_DAYS,
    ):
        self._log_dir = Path(log_dir)
        self._log_dir.mkdir(parents=True, exist_ok=True)
        self._buffer_size = buffer_size
        self._flush_interval = flush_interval
        self._retention_days = retention_days
        self._buffer: List[AuditEvent] = []
        self._lock = asyncio.Lock()
        self._flush_task: Optional[asyncio.Task] = None
        self._closed = False

    async def start(self):
        if self._flush_task is not None and not self._flush_task.done():
            return
        self._flush_task = asyncio.create_task(self._flush_loop())
        logger.info("Audit logger started: dir=%s", self._log_dir)

    async def stop(self):
        self._closed = True
        if self._flush_task:
            self._flush_task.cancel()
            try:
                await self._flush_task
            except asyncio.CancelledError:
                pass
        await self.flush()
        logger.info("Audit logger stopped")

    async def _flush_loop(self):
        while not self._closed:
            await asyncio.sleep(self._flush_interval)
            try:
                await self.flush()
                self._cleanup_old_logs()
            except Exception as e:
                logger.warning("Audit flush loop error: %s", e)

    def _current_log_file(self) -> Path:
        date_str = datetime.now().strftime("%Y-%m-%d")
        return self._log_dir / f"audit_{date_str}.jsonl"

    async def log(self, event: AuditEvent):
        async with self._lock:
            self._buffer.append(event)
            should_flush = len(self._buffer) >= self._buffer_size

        if should_flush:
            await self.flush()

    async def flush(self):
        async with self._lock:
            if not self._buffer:
                return
            events = self._buffer
            self._buffer = []

        if not events:
            return

        log_file = self._current_log_file()
        lines = [json.dumps(event.to_dict(), ensure_ascii=False) + "\n" for event in events]
        try:
            log_file.parent.mkdir(parents=True, exist_ok=True)
            await asyncio.to_thread(self._append_to_file, log_file, lines)
            logger.debug("Flushed %d audit events to %s", len(events), log_file.name)
        except Exception as e:
            logger.error("Failed to flush audit log: %s", e)

    def _append_to_file(self, file_path: Path, lines: List[str]):
        with open(file_path, "a", encoding="utf-8") as f:
            f.writelines(lines)

    def _cleanup_old_logs(self):
        try:
            cutoff = time.time() - self._retention_days * 86400
            for file_path in self._log_dir.glob("audit_*.jsonl"):
                if file_path.stat().st_mtime < cutoff:
                    file_path.unlink(missing_ok=True)
                    logger.debug("Removed old audit log: %s", file_path.name)
        except Exception as e:
            logger.warning("Audit log cleanup error: %s", e)

    async def query(
        self,
        user_id: Optional[str] = None,
        action: Optional[str] = None,
        resource_type: Optional[str] = None,
        resource_id: Optional[str] = None,
        status: Optional[str] = None,
        start_time: Optional[str] = None,
        end_time: Optional[str] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> List[Dict[str, Any]]:
        """简单审计日志查询（按时间倒序）。"""
        await self.flush()

        results = []
        log_files = sorted(self._log_dir.glob("audit_*.jsonl"), reverse=True)

        for file_path in log_files:
            try:
                file_events = await asyncio.to_thread(self._read_log_file, file_path)
                for event in file_events:
                    if user_id and event.get("user_id") != user_id:
                        continue
                    if action and event.get("action") != action:
                        continue
                    if resource_type and event.get("resource_type") != resource_type:
                        continue
                    if resource_id and event.get("resource_id") != resource_id:
                        continue
                    if status and event.get("status") != status:
                        continue
                    if start_time and event.get("timestamp", "") < start_time:
                        continue
                    if end_time and event.get("timestamp", "") > end_time:
                        continue
                    results.append(event)
                    if len(results) >= offset + limit:
                        break
                if len(results) >= offset + limit:
                    break
            except Exception as e:
                logger.warning("Failed to read audit log %s: %s", file_path.name, e)

        return results[offset:offset + limit]

    def _read_log_file(self, file_path: Path) -> List[Dict[str, Any]]:
        events = []
        if not file_path.exists():
            return events
        with open(file_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    events.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
        return events


audit_logger = AuditLogger()
