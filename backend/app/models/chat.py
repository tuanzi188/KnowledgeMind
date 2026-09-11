from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from enum import Enum
import uuid


class ReasoningMode(str, Enum):
    non_think = "non_think"
    think_high = "think_high"
    think_max = "think_max"


class ChunkingStrategy(str, Enum):
    fixed = "fixed"
    semantic = "semantic"
    structural = "structural"


class DocumentChunk(BaseModel):
    chunk_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    doc_id: str
    content: str
    metadata: Dict[str, Any] = Field(default_factory=dict, description="文档信息+内容信息+权限信息")
    embedding: Optional[List[float]] = None
    sparse_embedding: Optional[Dict[str, float]] = None


class RetrievalResult(BaseModel):
    chunk_id: str
    doc_id: str
    content: str
    metadata: Dict[str, Any] = {}
    score: float = 0.0
    source: str = "vector"


class Message(BaseModel):
    role: str = Field(..., pattern="^(user|assistant|system)$")
    content: str


class ChatRequest(BaseModel):
    query: str = Field(..., min_length=1, max_length=10000, description="用户问题")
    conversation_id: Optional[str] = None
    reasoning_mode: Optional[ReasoningMode] = None
    top_k: Optional[int] = Field(default=5, ge=1, le=20)
    temperature: Optional[float] = Field(default=0.1, ge=0.0, le=2.0)
    use_fallback: Optional[bool] = None


class Citation(BaseModel):
    document_id: str
    document_title: str
    page: Optional[int] = None
    paragraph: Optional[str] = None
    content: str
    score: float


class ChatSegment(BaseModel):
    text: str
    citations: List[Citation] = []


class ChatResponse(BaseModel):
    answer: str
    segments: List[ChatSegment] = []
    citations: List[Citation] = []
    reasoning_content: Optional[str] = None
    confidence_score: float = 0.0
    conversation_id: str
    token_usage: Optional[dict] = None
    model_used: str = ""
    reasoning_mode_used: str = ""
    is_fallback: bool = False


class DocumentUploadResponse(BaseModel):
    document_id: str
    filename: str
    status: str
    chunks_count: int = 0
    message: str = ""
    task_id: Optional[str] = None
    owner: Optional[str] = None
    is_public: Optional[bool] = False


class DocumentInfo(BaseModel):
    document_id: str
    filename: str
    title: str
    author: Optional[str] = None
    department: Optional[str] = None
    classification: Optional[str] = None
    file_type: str
    file_size: int
    upload_time: str
    chunks_count: int
    status: str
    owner: Optional[str] = None
    is_public: Optional[bool] = False
    allowed_users: Optional[List[str]] = []
    allowed_departments: Optional[List[str]] = []
    allowed_roles: Optional[List[str]] = []


class SearchRequest(BaseModel):
    query: str = Field(..., min_length=1)
    top_k: int = Field(default=10, ge=1, le=50)
    filters: Optional[dict] = None
    query_type: Optional[str] = Field(default="综合分析", description="检索权重类型，如 概念解释、精确查找、综合分析")


class SearchResult(BaseModel):
    document_id: str
    content: str
    score: float
    metadata: dict


class SearchResponse(BaseModel):
    results: List[SearchResult]
    total: int
    query: str


class FeedbackRequest(BaseModel):
    conversation_id: str
    message_index: int
    feedback_type: str = Field(..., pattern="^(thumbs_up|thumbs_down)$")
    detail: Optional[str] = None


class ErrorResponse(BaseModel):
    error_code: str
    message: str
    detail: Optional[str] = None


class ConversationTurn(BaseModel):
    query: str
    answer: str
    timestamp: float


class ConversationSummary(BaseModel):
    conversation_id: str
    created_at: float
    last_updated: float
    turn_count: int
    preview: str


class ConversationDetail(BaseModel):
    conversation_id: str
    created_at: float
    turns: List[ConversationTurn]


class ConversationListResponse(BaseModel):
    conversations: List[ConversationSummary]


class ConversationDeleteResponse(BaseModel):
    success: bool
    conversation_id: str
