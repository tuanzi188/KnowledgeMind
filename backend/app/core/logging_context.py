"""请求级日志上下文。

通过 contextvars 在中间件与业务代码之间传递 trace_id，
并在日志格式中统一输出，方便排查单次请求的全链路问题。
"""

import contextvars
import logging
import uuid

# 当前请求的 trace_id；未设置时为空字符串
trace_id_var: contextvars.ContextVar[str] = contextvars.ContextVar("trace_id", default="")


class TraceIdFilter(logging.Filter):
    """为每条日志记录注入 trace_id 字段。"""

    def filter(self, record: logging.LogRecord) -> bool:
        record.trace_id = trace_id_var.get() or "-"
        return True


class TraceIdFormatter(logging.Formatter):
    """兼容未注入 trace_id 的日志记录，避免 KeyError。"""

    def format(self, record: logging.LogRecord) -> str:
        if not hasattr(record, "trace_id"):
            record.trace_id = "-"
        return super().format(record)


def get_trace_id() -> str:
    """获取当前上下文中的 trace_id。"""
    return trace_id_var.get()


def generate_trace_id() -> str:
    """生成新的 trace_id。"""
    return uuid.uuid4().hex[:16]
