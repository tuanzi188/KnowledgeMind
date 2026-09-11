"""
Harness 韧性工程模块
- 熔断器 (Circuit Breaker): 连续失败后自动熔断，半开试探，自动恢复
- 退避重试 (Retry with Backoff): 指数退避 + 随机抖动，避免惊群效应
"""

import asyncio
import logging
import random
import time
from functools import wraps
from typing import Callable, Optional

logger = logging.getLogger(__name__)


class CircuitState:
    CLOSED = "closed"       # 正常，请求通过
    OPEN = "open"           # 熔断，请求直接拒绝
    HALF_OPEN = "half_open" # 半开，试探性放行一个请求


class CircuitBreaker:
    """熔断器：三态有限状态机"""

    def __init__(
        self,
        name: str,
        failure_threshold: int = 5,
        recovery_timeout: float = 30.0,
        half_open_max_requests: int = 1,
    ):
        self.name = name
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.half_open_max_requests = half_open_max_requests

        self._state = CircuitState.CLOSED
        self._failure_count = 0
        self._last_failure_time: float = 0.0
        self._half_open_requests = 0
        self._success_count = 0
        self._total_count = 0

    @property
    def state(self) -> str:
        return self._state

    @property
    def stats(self) -> dict:
        return {
            "state": self._state,
            "failure_count": self._failure_count,
            "success_count": self._success_count,
            "total_count": self._total_count,
        }

    def _transition_to(self, new_state: str):
        old_state = self._state
        self._state = new_state
        if new_state == CircuitState.OPEN:
            logger.warning("[%s] 熔断器打开 (OPEN) — 连续失败 %s 次", self.name, self._failure_count)
        elif new_state == CircuitState.HALF_OPEN:
            logger.info("[%s] 熔断器半开 (HALF_OPEN) — 试探性恢复", self.name)
        elif new_state == CircuitState.CLOSED:
            logger.info("[%s] 熔断器关闭 (CLOSED) — 已恢复", self.name)
            self._failure_count = 0

    def _should_attempt_recovery(self) -> bool:
        if self._state != CircuitState.OPEN:
            return False
        elapsed = time.monotonic() - self._last_failure_time
        return elapsed >= self.recovery_timeout

    def before_call(self):
        """调用前检查：是否允许请求通过"""
        if self._state == CircuitState.CLOSED:
            return

        if self._state == CircuitState.OPEN:
            if self._should_attempt_recovery():
                self._transition_to(CircuitState.HALF_OPEN)
                self._half_open_requests = 0
            else:
                raise CircuitBreakerOpenError(
                    f"[{self.name}] 熔断器中，请求被拒绝 "
                    f"(剩余 {self.recovery_timeout - (time.monotonic() - self._last_failure_time):.1f}s)"
                )

        if self._state == CircuitState.HALF_OPEN:
            if self._half_open_requests >= self.half_open_max_requests:
                raise CircuitBreakerOpenError(
                    f"[{self.name}] 半开状态已达最大试探请求数，请稍后重试"
                )
            self._half_open_requests += 1

    def on_success(self):
        """调用成功后通知"""
        self._total_count += 1
        self._success_count += 1

        if self._state == CircuitState.HALF_OPEN:
            self._transition_to(CircuitState.CLOSED)

    def on_failure(self):
        """调用失败后通知"""
        self._total_count += 1
        self._failure_count += 1
        self._last_failure_time = time.monotonic()

        if self._state == CircuitState.HALF_OPEN:
            self._transition_to(CircuitState.OPEN)
        elif self._state == CircuitState.CLOSED and self._failure_count >= self.failure_threshold:
            self._transition_to(CircuitState.OPEN)

    def reset(self):
        """手动重置熔断器"""
        self._state = CircuitState.CLOSED
        self._failure_count = 0
        self._half_open_requests = 0
        self._last_failure_time = 0.0
        logger.info("[%s] 熔断器已手动重置", self.name)


class CircuitBreakerOpenError(Exception):
    """熔断器打开时抛出的异常"""
    pass


def _is_client_error(err: Exception) -> bool:
    """判断异常是否为 4xx 客户端错误（如 OpenAI 的 APIStatusError）"""
    status_code = getattr(err, "status_code", None)
    return isinstance(status_code, int) and 400 <= status_code <= 499


class CircuitBreakerRegistry:
    """全局熔断器注册表，便于健康检查时查询状态"""

    def __init__(self):
        self._breakers: dict[str, CircuitBreaker] = {}

    def get_or_create(
        self,
        name: str,
        failure_threshold: int = 5,
        recovery_timeout: float = 30.0,
    ) -> CircuitBreaker:
        if name not in self._breakers:
            self._breakers[name] = CircuitBreaker(
                name=name,
                failure_threshold=failure_threshold,
                recovery_timeout=recovery_timeout,
            )
        return self._breakers[name]

    def get_all_states(self) -> dict:
        return {name: cb.stats for name, cb in self._breakers.items()}

    def reset_all(self):
        for cb in self._breakers.values():
            cb.reset()


circuit_breaker_registry = CircuitBreakerRegistry()


async def retry_with_backoff(
    coro_factory: Callable,
    max_retries: int = 3,
    base_delay: float = 1.0,
    max_delay: float = 30.0,
    backoff_factor: float = 2.0,
    jitter: bool = True,
    retryable_exceptions: tuple = (Exception,),
):
    """
    退避重试：指数退避 + 随机抖动

    参数:
        coro_factory: 返回协程的可调用对象（每次重试都会重新调用）
        max_retries: 最大重试次数
        base_delay: 基础延迟（秒）
        max_delay: 最大延迟（秒）
        backoff_factor: 退避因子
        jitter: 是否添加随机抖动
        retryable_exceptions: 可重试的异常类型
    """
    last_exception = None
    for attempt in range(max_retries + 1):
        try:
            return await coro_factory()
        except retryable_exceptions as e:
            last_exception = e
            if attempt < max_retries:
                delay = min(base_delay * (backoff_factor ** attempt), max_delay)
                if jitter:
                    delay *= 0.5 + random.random()  # 50%~150% 抖动
                logger.warning(
                    "重试 %s/%s，等待 %.1fs: %s",
                    attempt + 1, max_retries, delay, str(e)[:200],
                )
                await asyncio.sleep(delay)
            else:
                logger.error("重试 %s 次后仍然失败: %s", max_retries, str(e)[:200])
    raise last_exception


def with_circuit_breaker(
    breaker_name: str,
    failure_threshold: int = 5,
    recovery_timeout: float = 30.0,
    fallback_value=None,
):
    """
    装饰器：为异步函数添加熔断器保护

    用法:
        @with_circuit_breaker("deepseek_api")
        async def call_api():
            ...
    """
    def decorator(func):
        breaker = circuit_breaker_registry.get_or_create(
            name=breaker_name,
            failure_threshold=failure_threshold,
            recovery_timeout=recovery_timeout,
        )

        @wraps(func)
        async def wrapper(*args, **kwargs):
            breaker.before_call()
            try:
                result = await func(*args, **kwargs)
                breaker.on_success()
                return result
            except CircuitBreakerOpenError:
                raise
            except Exception as e:
                # 4xx 客户端错误不应视为服务端故障，不计入熔断
                if _is_client_error(e):
                    raise
                breaker.on_failure()
                if fallback_value is not None:
                    logger.warning(
                        "[%s] 熔断降级，返回 fallback: %s", breaker_name, str(e)[:200]
                    )
                    return fallback_value
                raise

        return wrapper
    return decorator