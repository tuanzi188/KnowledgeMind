from typing import Any


def _match_operator(field_value: Any, op: str, operand: Any) -> bool:
    """匹配单个 ChromaDB 风格操作符。"""
    if op == "$eq":
        return field_value == operand
    if op == "$ne":
        return field_value != operand
    if op == "$gt":
        return field_value > operand
    if op == "$gte":
        return field_value >= operand
    if op == "$lt":
        return field_value < operand
    if op == "$lte":
        return field_value <= operand
    if op == "$in":
        return field_value in operand
    if op == "$nin":
        return field_value not in operand
    # 未知操作符默认不匹配
    return False


def match_filters(metadata: dict, filters: dict) -> bool:
    """按过滤条件匹配元数据。

    支持两种风格：
    1. 简单过滤：{"key": "value"} 或 {"key": ["v1", "v2"]}
    2. ChromaDB 操作符：{"key": {"$eq": "value", "$gt": 1}}
    """
    for key, value in filters.items():
        if key not in metadata:
            return False

        if isinstance(value, dict):
            # ChromaDB 风格操作符
            for op, operand in value.items():
                if not _match_operator(metadata[key], op, operand):
                    return False
        elif isinstance(value, list):
            if metadata[key] not in value:
                return False
        elif isinstance(value, str):
            if metadata[key] != value:
                return False
        else:
            if metadata[key] != value:
                return False
    return True
