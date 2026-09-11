from pydantic import BaseModel, Field
from typing import Optional, Dict, Any, List
from datetime import datetime


class AuditLogQueryRequest(BaseModel):
    user_id: Optional[str] = None
    action: Optional[str] = None
    resource_type: Optional[str] = None
    resource_id: Optional[str] = None
    status: Optional[str] = None
    start_time: Optional[str] = None
    end_time: Optional[str] = None
    limit: int = Field(default=100, ge=1, le=1000)
    offset: int = Field(default=0, ge=0)


class AuditLogQueryResponse(BaseModel):
    total: int
    logs: List[Dict[str, Any]]


class AnalyticsTimeRange(BaseModel):
    start: Optional[str] = Field(None, description="开始时间 ISO 格式")
    end: Optional[str] = Field(None, description="结束时间 ISO 格式")


class DocumentAnalyticsRequest(BaseModel):
    time_range: Optional[AnalyticsTimeRange] = None
    group_by: Optional[str] = Field(default="file_type", description="分组维度: file_type, department, classification")


class ConversationAnalyticsRequest(BaseModel):
    time_range: Optional[AnalyticsTimeRange] = None
    group_by: Optional[str] = Field(default="day", description="分组维度: day, week, month")


class TaskAnalyticsRequest(BaseModel):
    time_range: Optional[AnalyticsTimeRange] = None
    group_by: Optional[str] = Field(default="status", description="分组维度: status, name")


class GraphAnalyticsRequest(BaseModel):
    top_k: int = Field(default=20, ge=1, le=100, description="Top-K 高频实体")


class AnalyticsResponse(BaseModel):
    metric: str
    summary: Dict[str, Any]
    series: List[Dict[str, Any]] = []
    detail: Optional[Dict[str, Any]] = None
    generated_at: str = Field(default_factory=lambda: datetime.now().isoformat())
