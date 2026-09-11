import os
import uuid
import asyncio
import logging
from datetime import datetime
from pathlib import Path
from fastapi import APIRouter, UploadFile, File, HTTPException, Form, Request
from typing import Optional, List

from app.config import DATA_DIR, MAX_UPLOAD_SIZE_BYTES, MAX_UPLOAD_SIZE_MB
from app.core.user_context import extract_user_context, UserContext
from app.models.chat import DocumentUploadResponse, ChunkingStrategy, DocumentChunk, DocumentInfo
from app.services.document_parser import parse_document, SUPPORTED_EXTENSIONS
from app.services.chunker import ChunkingPipeline
from app.services.vector_store import vector_store
from app.services.keyword_search import get_bm25_searcher
from app.services.graph_search import graph_searcher
from app.services.embedding import get_embedding
from app.services.task_queue import task_queue
from app.services.audit_logger import audit_logger, AuditAction, AuditStatus, AuditEvent
from app.services.access_control import (
    can_access,
    can_manage,
    filter_accessible_records,
    build_acl_metadata,
    merge_acl_into_metadata,
)

logger = logging.getLogger(__name__)
router = APIRouter()

# 细粒度索引锁：向量库写入由底层保证/队列串行；BM25 与图谱索引各自加锁，避免互相阻塞。
_bm25_lock = asyncio.Lock()
_graph_lock = asyncio.Lock()

UPLOAD_DIR = DATA_DIR / "uploads"
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

chunking_pipeline = ChunkingPipeline()


async def _index_document_task(chunks_data: list[dict], parsed_content: str, doc_id: str):
    """任务队列执行的文档索引任务（可重试）。

    设计要点：
    1. 向量写入与 BM25/图谱索引解耦，使用细粒度锁避免单把大锁阻塞所有上传。
    2. 图谱实体抽取（正则/CPU）在锁外执行，仅在写入索引时加锁。
    3. 落盘操作跟随对应索引的写锁，保证一致性；不同索引的保存互不阻塞。
    """
    bm25 = get_bm25_searcher()

    # 1. 重建 DocumentChunk 并生成 sparse embedding（只读访问 bm25，可放锁外）
    chunks: list[DocumentChunk] = []
    for cd in chunks_data:
        chunk = DocumentChunk(
            chunk_id=cd["chunk_id"],
            doc_id=cd["doc_id"],
            content=cd["content"],
            metadata=cd["metadata"],
        )
        chunk.sparse_embedding = bm25.generate_sparse_embedding(chunk.content)
        chunks.append(chunk)

    # 2. 写入向量库（队列已串行化任务，ChromaDB 写操作独立进行）
    await vector_store.add_chunks(chunks)

    # 3. 加 BM25 锁写入并落盘
    async with _bm25_lock:
        for chunk in chunks:
            bm25.add_document({
                "chunk_id": chunk.chunk_id,
                "doc_id": chunk.doc_id,
                "content": chunk.content,
                "metadata": chunk.metadata,
            })
        bm25.save_to_disk()

    # 4. 图谱实体抽取在锁外执行（避免阻塞 BM25）
    entities = graph_searcher.extract_entities_from_text(parsed_content)
    chunk_ids = [c.chunk_id for c in chunks]

    # 5. 加图谱锁写入并落盘
    async with _graph_lock:
        for entity in entities:
            graph_searcher.add_entity(entity["name"], chunk_ids, document_id=doc_id)
        graph_searcher.save_to_disk()

    logger.info("Indexing complete for document %s: %s chunks", doc_id, len(chunks))
    return {"chunks_indexed": len(chunks)}


@router.post("/upload", response_model=DocumentUploadResponse)
async def upload_document(
    request: Request,
    file: UploadFile = File(...),
    title: Optional[str] = Form(None),
    chunking_strategy: Optional[str] = Form("semantic"),
    ocr_enabled: bool = Form(False),
    allowed_users: Optional[str] = Form(None, description="逗号分隔的允许访问用户 ID"),
    allowed_departments: Optional[str] = Form(None, description="逗号分隔的允许访问部门"),
    allowed_roles: Optional[str] = Form(None, description="逗号分隔的允许访问角色"),
    is_public: bool = Form(False, description="是否公开访问"),
):
    user_context = extract_user_context(request)
    start_time = asyncio.get_event_loop().time()

    ext = os.path.splitext(file.filename or "")[1].lower()
    if ext not in SUPPORTED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type: {ext}. Supported: {', '.join(SUPPORTED_EXTENSIONS)}",
        )

    content_length = file.size
    if content_length is not None and content_length > MAX_UPLOAD_SIZE_BYTES:
        raise HTTPException(
            status_code=413,
            detail=f"File too large ({content_length} bytes). Maximum allowed size is {MAX_UPLOAD_SIZE_MB}MB",
        )

    content = await file.read()
    if len(content) > MAX_UPLOAD_SIZE_BYTES:
        raise HTTPException(
            status_code=413,
            detail=f"File too large ({len(content)} bytes). Maximum allowed size is {MAX_UPLOAD_SIZE_MB}MB",
        )

    doc_id = str(uuid.uuid4())
    safe_filename = f"{doc_id}{ext}"
    file_path = UPLOAD_DIR / safe_filename
    with open(file_path, "wb") as f:
        f.write(content)

    # 文档解析可能涉及 OCR 等 CPU/IO 密集型操作，放到线程池避免阻塞上传接口
    parsed = await asyncio.to_thread(parse_document, str(file_path), ocr_enabled=ocr_enabled)
    if parsed is None or not parsed.content.strip():
        raise HTTPException(status_code=400, detail="Failed to parse document or document is empty")

    base_metadata = {
        "document_id": doc_id,
        "filename": file.filename,
        "title": title or parsed.metadata.get("title", file.filename or "Untitled"),
        "file_type": parsed.metadata.get("file_type", ext.lstrip(".")),
        "file_size": parsed.metadata.get("file_size", len(content)),
        "source": parsed.metadata.get("source", "local_upload"),
        "author": parsed.metadata.get("author", ""),
        "department": parsed.metadata.get("department", ""),
        "classification": parsed.metadata.get("classification", "internal"),
        "page_count": parsed.metadata.get("page_count", 0),
        "upload_time": datetime.now().isoformat(),
    }

    acl = build_acl_metadata(
        user_context,
        allowed_users=allowed_users,
        allowed_departments=allowed_departments,
        allowed_roles=allowed_roles,
        is_public=is_public,
    )
    document_metadata = merge_acl_into_metadata(base_metadata, acl)

    strategy = ChunkingStrategy(chunking_strategy) if chunking_strategy in [s.value for s in ChunkingStrategy] else ChunkingStrategy.semantic

    emb = get_embedding()
    # 语义分块涉及 Embedding 编码，同样放到线程池执行
    chunks: list[DocumentChunk] = await asyncio.to_thread(
        chunking_pipeline.create_chunks,
        document_id=doc_id,
        content=parsed.content,
        metadata=document_metadata,
        strategy=strategy,
        embeddings_fn=emb.embed if strategy == ChunkingStrategy.semantic else None,
    )

    if not chunks:
        raise HTTPException(status_code=400, detail="No content chunks extracted")

    # 序列化 chunks 为 dict（任务队列中需跨协程传递）
    chunks_data = [
        {
            "chunk_id": c.chunk_id,
            "doc_id": c.doc_id,
            "content": c.content,
            "metadata": c.metadata,
        }
        for c in chunks
    ]

    task_id = await task_queue.submit(
        f"index:{file.filename or 'unknown'}",
        _index_document_task,
        chunks_data,
        parsed.content,
        doc_id,
    )

    logger.info(
        "Document upload queued: %s, %s chunks, task=%s, strategy=%s",
        file.filename, len(chunks), task_id, strategy.value,
    )

    duration_ms = (asyncio.get_event_loop().time() - start_time) * 1000
    await audit_logger.log(
        AuditEvent(
            user_context=user_context,
            action=AuditAction.DOCUMENT_UPLOAD,
            resource_type="document",
            resource_id=doc_id,
            status=AuditStatus.SUCCESS,
            duration_ms=duration_ms,
            details={
                "filename": file.filename,
                "file_type": document_metadata.get("file_type"),
                "file_size": document_metadata.get("file_size"),
                "chunks_count": len(chunks),
                "strategy": strategy.value,
                "is_public": is_public,
            },
        )
    )

    return DocumentUploadResponse(
        document_id=doc_id,
        filename=file.filename or "unknown",
        status="success",
        chunks_count=len(chunks),
        message=f"Queued {len(chunks)} chunks ({strategy.value} strategy). Task: {task_id}",
        task_id=task_id,
        owner=user_context.user_id,
        is_public=is_public,
    )


@router.get("/documents")
async def list_documents(request: Request):
    """列出当前用户有权限访问的文档（按 document_id 聚合）。"""
    user_context = extract_user_context(request)
    start_time = asyncio.get_event_loop().time()

    chunks = await vector_store.list_chunks()
    chunks = filter_accessible_records(user_context, chunks)

    doc_map: dict[str, dict] = {}

    for chunk in chunks:
        metadata = chunk.get("metadata", {})
        doc_id = str(metadata.get("document_id", "")).strip()
        if not doc_id:
            continue

        if doc_id not in doc_map:
            doc_map[doc_id] = {
                "document_id": doc_id,
                "filename": metadata.get("filename", "未知"),
                "title": metadata.get("title", metadata.get("filename", "未知")),
                "author": metadata.get("author"),
                "department": metadata.get("department"),
                "classification": metadata.get("classification", "internal"),
                "file_type": metadata.get("file_type", "unknown"),
                "file_size": int(metadata.get("file_size", 0)),
                "upload_time": metadata.get("upload_time", ""),
                "chunks_count": 0,
                "status": "indexed",
                "owner": metadata.get("owner"),
                "is_public": metadata.get("is_public", False),
                "allowed_users": metadata.get("allowed_users", []),
                "allowed_departments": metadata.get("allowed_departments", []),
                "allowed_roles": metadata.get("allowed_roles", []),
            }
        doc_map[doc_id]["chunks_count"] += 1

    documents = list(doc_map.values())
    documents.sort(key=lambda d: d.get("upload_time", ""), reverse=True)

    duration_ms = (asyncio.get_event_loop().time() - start_time) * 1000
    await audit_logger.log(
        AuditEvent(
            user_context=user_context,
            action=AuditAction.DOCUMENT_LIST,
            resource_type="document",
            status=AuditStatus.SUCCESS,
            duration_ms=duration_ms,
            details={"total_visible": len(documents)},
        )
    )

    return {"documents": documents, "total": len(documents)}


@router.delete("/documents/{document_id}")
async def delete_document(document_id: str, request: Request):
    """删除文档，仅管理员或 owner 可执行。"""
    user_context = extract_user_context(request)
    start_time = asyncio.get_event_loop().time()

    # 获取文档元数据用于权限校验
    all_chunks = await vector_store.list_chunks()
    doc_metadata = None
    for chunk in all_chunks:
        metadata = chunk.get("metadata", {}) or {}
        if str(metadata.get("document_id", "")).strip() == document_id:
            doc_metadata = metadata
            break

    if doc_metadata is None:
        duration_ms = (asyncio.get_event_loop().time() - start_time) * 1000
        await audit_logger.log(
            AuditEvent(
                user_context=user_context,
                action=AuditAction.DOCUMENT_DELETE,
                resource_type="document",
                resource_id=document_id,
                status=AuditStatus.FAILURE,
                duration_ms=duration_ms,
                error_message="Document not found",
            )
        )
        raise HTTPException(status_code=404, detail="Document not found")

    if not can_manage(user_context, doc_metadata):
        duration_ms = (asyncio.get_event_loop().time() - start_time) * 1000
        await audit_logger.log(
            AuditEvent(
                user_context=user_context,
                action=AuditAction.DOCUMENT_DELETE,
                resource_type="document",
                resource_id=document_id,
                status=AuditStatus.DENIED,
                duration_ms=duration_ms,
                details={"owner": doc_metadata.get("owner")},
            )
        )
        raise HTTPException(status_code=403, detail="Permission denied")

    await vector_store.delete_document(document_id)
    bm25 = get_bm25_searcher()
    bm25.delete_document(document_id)
    bm25.save_to_disk()
    graph_searcher.delete_document(document_id)
    graph_searcher.save_to_disk()

    duration_ms = (asyncio.get_event_loop().time() - start_time) * 1000
    await audit_logger.log(
        AuditEvent(
            user_context=user_context,
            action=AuditAction.DOCUMENT_DELETE,
            resource_type="document",
            resource_id=document_id,
            status=AuditStatus.SUCCESS,
            duration_ms=duration_ms,
            details={"filename": doc_metadata.get("filename")},
        )
    )

    return {"status": "deleted", "document_id": document_id}


@router.get("/stats")
async def get_stats():
    count = await vector_store.count()
    return {"total_chunks": count, "status": "ok"}


@router.get("/tasks/{task_id}")
async def get_task_status(task_id: str):
    """查询索引任务状态。"""
    task = await task_queue.get_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    return task


@router.get("/tasks")
async def list_tasks(status: Optional[str] = None, limit: int = 50):
    """列出索引任务。"""
    tasks = await task_queue.list_tasks(status=status, limit=limit)
    return {"tasks": tasks, "count": len(tasks)}
