import asyncio
import json
import logging
import time
import uuid
from enum import Enum
from typing import Any, Callable, Dict, Optional, Awaitable

from app.config import CACHE_CONFIG

logger = logging.getLogger(__name__)

TASK_QUEUE_MAX_SIZE = 100
TASK_RETRY_MAX = 3
TASK_RETRY_DELAY_BASE = 2.0
REDIS_TASK_PREFIX = "km:task:"


class TaskStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class Task:
    __slots__ = (
        "task_id", "name", "status", "created_at", "started_at",
        "finished_at", "result", "error", "retry_count",
    )

    def __init__(self, task_id: str, name: str):
        self.task_id = task_id
        self.name = name
        self.status = TaskStatus.PENDING
        self.created_at = time.time()
        self.started_at: float | None = None
        self.finished_at: float | None = None
        self.result: Any = None
        self.error: str | None = None
        self.retry_count: int = 0

    def to_dict(self) -> dict:
        return {
            "task_id": self.task_id,
            "name": self.name,
            "status": self.status.value,
            "created_at": self.created_at,
            "started_at": self.started_at,
            "finished_at": self.finished_at,
            "error": self.error,
            "retry_count": self.retry_count,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Task":
        task = cls(task_id=data["task_id"], name=data["name"])
        task.status = TaskStatus(data.get("status", "pending"))
        task.created_at = data.get("created_at", time.time())
        task.started_at = data.get("started_at")
        task.finished_at = data.get("finished_at")
        task.error = data.get("error")
        task.retry_count = data.get("retry_count", 0)
        return task


class TaskQueue:
    """异步任务队列 — 基于 asyncio.Queue + Redis（可选）的轻量级实现。

    特性:
    - 内存队列 + Worker 协程处理
    - Redis 可选：跨 worker 状态共享
    - 自动重试（最多 3 次，指数退避）
    - 任务状态查询 API
    """

    def __init__(self):
        self._queue: asyncio.Queue[tuple[Task, Callable[..., Awaitable[Any]], tuple, dict]] = (
            asyncio.Queue(maxsize=TASK_QUEUE_MAX_SIZE)
        )
        self._tasks: Dict[str, Task] = {}
        self._redis = None
        self._redis_available = False
        self._worker_task: asyncio.Task | None = None
        self._max_retry = TASK_RETRY_MAX
        self._retry_base_delay = TASK_RETRY_DELAY_BASE

    async def start(self):
        """启动任务队列 Worker。"""
        if self._worker_task and not self._worker_task.done():
            return
        self._worker_task = asyncio.create_task(self._worker_loop())
        logger.info("Task queue worker started")

        # 尝试连接 Redis
        redis_url = CACHE_CONFIG.get("redis_url", "")
        if redis_url:
            try:
                import redis.asyncio as aioredis
                self._redis = aioredis.from_url(
                    redis_url,
                    encoding="utf-8",
                    decode_responses=True,
                    socket_connect_timeout=2,
                )
                await self._redis.ping()
                self._redis_available = True
                logger.info("Task queue: Redis connected for cross-worker status sharing")
            except Exception as e:
                logger.warning("Task queue: Redis unavailable (%s), using in-memory only", e)

    async def stop(self):
        """停止任务队列。"""
        if self._worker_task:
            self._worker_task.cancel()
            try:
                await self._worker_task
            except asyncio.CancelledError:
                pass
            self._worker_task = None
            logger.info("Task queue worker stopped")

    async def submit(
        self,
        name: str,
        func: Callable[..., Awaitable[Any]],
        *args,
        **kwargs,
    ) -> str:
        """提交任务到队列，返回 task_id。"""
        task_id = str(uuid.uuid4())
        task = Task(task_id=task_id, name=name)
        self._tasks[task_id] = task

        await self._persist_task_status(task)
        await self._queue.put((task, func, args, kwargs))
        logger.info("Task submitted: %s (%s)", task_id, name)
        return task_id

    async def get_task(self, task_id: str) -> Optional[dict]:
        """查询任务状态。"""
        await self.cleanup_old_tasks()
        task = self._tasks.get(task_id)
        if task:
            return task.to_dict()

        # 尝试从 Redis 恢复
        if self._redis_available:
            try:
                data_str = await self._redis.get(f"{REDIS_TASK_PREFIX}{task_id}")
                if data_str:
                    data = json.loads(data_str)
                    task = Task.from_dict(data)
                    self._tasks[task_id] = task
                    return task.to_dict()
            except Exception as e:
                logger.debug("Failed to restore task %s from Redis: %s", task_id, e)
        return None

    async def list_tasks(self, status: Optional[str] = None, limit: int = 50) -> list[dict]:
        """列出任务。"""
        await self.cleanup_old_tasks()
        result = []
        for task in reversed(list(self._tasks.values())):
            if status and task.status.value != status:
                continue
            result.append(task.to_dict())
            if len(result) >= limit:
                break
        return result

    async def _worker_loop(self):
        """Worker 主循环，从队列取任务并执行。"""
        while True:
            try:
                task, func, args, kwargs = await self._queue.get()
                await self._execute_task(task, func, args, kwargs)
                self._queue.task_done()
                await self.cleanup_old_tasks()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error("Task queue worker error: %s", e)
                await asyncio.sleep(1)

    async def _execute_task(
        self,
        task: Task,
        func: Callable[..., Awaitable[Any]],
        args: tuple,
        kwargs: dict,
    ):
        """执行单个任务，带重试。"""
        task.status = TaskStatus.RUNNING
        task.started_at = time.time()
        await self._persist_task_status(task)

        for attempt in range(self._max_retry + 1):
            try:
                result = await func(*args, **kwargs)
                task.status = TaskStatus.COMPLETED
                task.result = result
                task.finished_at = time.time()
                await self._persist_task_status(task)
                logger.info("Task completed: %s (%s) after %d retries",
                            task.task_id, task.name, task.retry_count)
                return
            except Exception as e:
                task.retry_count = attempt + 1
                task.error = str(e)
                if attempt < self._max_retry:
                    delay = self._retry_base_delay * (2 ** attempt)
                    logger.warning(
                        "Task %s (%s) failed (attempt %d/%d), retrying in %.1fs: %s",
                        task.task_id, task.name, attempt + 1, self._max_retry, delay, e,
                    )
                    await asyncio.sleep(delay)
                else:
                    task.status = TaskStatus.FAILED
                    task.finished_at = time.time()
                    await self._persist_task_status(task)
                    logger.error(
                        "Task %s (%s) failed after %d retries: %s",
                        task.task_id, task.name, task.retry_count, e,
                    )

    async def _persist_task_status(self, task: Task):
        """将任务状态持久化到 Redis（如可用）。"""
        if not self._redis_available or not self._redis:
            return
        try:
            await self._redis.setex(
                f"{REDIS_TASK_PREFIX}{task.task_id}",
                86400,  # 24h TTL
                json.dumps(task.to_dict(), ensure_ascii=False),
            )
        except Exception as e:
            logger.debug("Failed to persist task status to Redis: %s", e)

    async def cleanup_old_tasks(self, older_than_seconds: int = 3600):
        """清理已完成/失败的任务记录。"""
        now = time.time()
        to_remove = []
        for tid, task in self._tasks.items():
            if task.finished_at and (now - task.finished_at) > older_than_seconds:
                to_remove.append(tid)
        for tid in to_remove:
            del self._tasks[tid]
            if self._redis_available:
                try:
                    await self._redis.delete(f"{REDIS_TASK_PREFIX}{tid}")
                except Exception as e:
                    logger.debug("Failed to delete old task %s from Redis: %s", tid, e)
        if to_remove:
            logger.debug("Cleaned up %d old task records", len(to_remove))


task_queue = TaskQueue()