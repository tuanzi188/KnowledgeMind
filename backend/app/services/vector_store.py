import os
import asyncio
import shutil
import logging
from functools import lru_cache
from typing import AsyncGenerator, List, Optional, Sequence

from app.config import VECTOR_STORE_CONFIG
from app.models.chat import DocumentChunk
from app.services.embedding import get_embedding, init_embedding

logger = logging.getLogger(__name__)

_EMBEDDING_DIM = VECTOR_STORE_CONFIG.get("embedding_dimension", 512)


@lru_cache(maxsize=1024)
def _cached_embed_query(query_text: str) -> list[float]:
    """查询 embedding 缓存：高频问题避免重复编码。"""
    return get_embedding().embed([query_text])[0]


class SemanticEmbeddingFn:
    def name(self):
        return "semantic_embedding"

    def __call__(self, input: Sequence[str]) -> Sequence[Sequence[float]]:
        return get_embedding().embed(list(input))

    def embed(self, texts: List[str]) -> List[List[float]]:
        return list(self.__call__(texts))


class VectorStore:
    def __init__(self):
        self._collection = None
        self._initialized = False
        self._ef = SemanticEmbeddingFn()
        self._memory_store: list[dict] = []

    async def initialize(self):
        if self._initialized:
            return

        persist_dir = VECTOR_STORE_CONFIG["persist_dir"]
        collection_name = VECTOR_STORE_CONFIG["collection_name"]

        init_embedding(dim=_EMBEDDING_DIM)

        try:
            import chromadb
            from chromadb.config import Settings

            _safely_migrate_embedding_store(persist_dir)

            client = chromadb.PersistentClient(
                path=persist_dir,
                settings=Settings(anonymized_telemetry=False),
            )

            self._collection = client.get_or_create_collection(
                name=collection_name,
                metadata={"hnsw:space": "cosine"},
                embedding_function=self._ef,
            )
            self._initialized = True
            logger.info(
                "ChromaDB initialized at %s with semantic embedding backend=%s",
                persist_dir,
                get_embedding().version_tag,
            )
        except Exception as vector_store_init_error:
            logger.warning(
                "ChromaDB initialization failed: %s, using in-memory fallback",
                vector_store_init_error,
            )
            self._use_memory_fallback()

    def _use_memory_fallback(self):
        self._memory_store = []
        self._initialized = True

    async def add_chunks(self, chunks: List[DocumentChunk]):
        if not chunks:
            return

        if self._collection is not None:
            chunk_ids = [chunk_item.chunk_id for chunk_item in chunks]
            chunk_documents = [chunk_item.content for chunk_item in chunks]
            chunk_metadatas = [
                {
                    key: str(value) if not isinstance(value, (str, int, float, bool)) else value
                    for key, value in chunk_item.metadata.items()
                }
                for chunk_item in chunks
            ]
            try:
                # CPU 密集型编码放到线程池，避免阻塞事件循环
                chunk_embeddings = await asyncio.to_thread(self._ef.embed, chunk_documents)
                self._collection.add(
                    ids=chunk_ids,
                    embeddings=chunk_embeddings,
                    documents=chunk_documents,
                    metadatas=chunk_metadatas,
                )
            except Exception as add_chunk_error:
                logger.error("Failed to add chunks to ChromaDB: %s", add_chunk_error)
                for chunk_item in chunks:
                    self._memory_store.append({
                        "id": chunk_item.chunk_id,
                        "content": chunk_item.content,
                        "metadata": chunk_item.metadata,
                    })
        else:
            for chunk_item in chunks:
                self._memory_store.append({
                    "id": chunk_item.chunk_id,
                    "content": chunk_item.content,
                    "metadata": chunk_item.metadata,
                })

    async def similarity_search(
        self,
        query_text: str,
        top_k: int = 10,
        filters: Optional[dict] = None,
    ) -> List[dict]:
        if self._collection is not None:
            where_clause = None
            if filters:
                where_clause = {}
                for filter_key, filter_value in filters.items():
                    if isinstance(filter_value, str):
                        where_clause[filter_key] = {"$eq": filter_value}
                    elif isinstance(filter_value, list):
                        where_clause[filter_key] = {"$in": filter_value}

            # 查询 embedding 使用线程池 + LRU 缓存，减少高频查询的 CPU 占用
            query_embedding = await asyncio.to_thread(_cached_embed_query, query_text)
            query_results = self._collection.query(
                query_embeddings=[query_embedding],
                n_results=top_k,
                where=where_clause,
            )
            if not query_results["ids"] or not query_results["ids"][0]:
                return []

            output_results: List[dict] = []
            for result_index in range(len(query_results["ids"][0])):
                output_results.append({
                    "chunk_id": query_results["ids"][0][result_index],
                    "content": query_results["documents"][0][result_index],
                    "metadata": query_results["metadatas"][0][result_index] if query_results["metadatas"] else {},
                    "score": 1.0 - (query_results["distances"][0][result_index] if query_results["distances"] else 0.0),
                })
            return output_results

        query_text_lower = query_text.lower()
        scored_results = []
        for memory_item in self._memory_store:
            match_score = 1.0 if query_text_lower in memory_item["content"].lower() else 0.0
            if match_score > 0:
                scored_results.append({
                    "chunk_id": memory_item["id"],
                    "content": memory_item["content"],
                    "metadata": memory_item["metadata"],
                    "score": match_score,
                })
        return scored_results[:top_k]

    async def delete_document(self, document_id: str):
        if self._collection is not None:
            collection_results = self._collection.get(where={"document_id": {"$eq": document_id}})
            if collection_results["ids"]:
                self._collection.delete(ids=collection_results["ids"])
        else:
            self._memory_store = [
                memory_item
                for memory_item in self._memory_store
                if memory_item["metadata"].get("document_id") != document_id
            ]

    async def count(self) -> int:
        if self._collection is not None:
            return self._collection.count()
        return len(self._memory_store)

    async def list_chunks(self, page_size: int = 1000) -> List[dict]:
        if page_size < 1:
            page_size = 1000
        if self._collection is not None:
            listed_chunks: List[dict] = []
            offset = 0
            while True:
                collection_results = self._collection.get(
                    include=["documents", "metadatas"],
                    limit=page_size,
                    offset=offset,
                )
                chunk_ids = collection_results.get("ids", [])
                if not chunk_ids:
                    break
                chunk_documents = collection_results.get("documents", [])
                chunk_metadatas = collection_results.get("metadatas", [])
                for chunk_index, chunk_id in enumerate(chunk_ids):
                    listed_chunks.append({
                        "chunk_id": chunk_id,
                        "content": chunk_documents[chunk_index] if chunk_index < len(chunk_documents) else "",
                        "metadata": chunk_metadatas[chunk_index] if chunk_index < len(chunk_metadatas) else {},
                    })
                offset += len(chunk_ids)
            return listed_chunks

        return [
            {
                "chunk_id": memory_item["id"],
                "content": memory_item["content"],
                "metadata": memory_item["metadata"],
            }
            for memory_item in self._memory_store
        ]

    async def list_chunks_stream(
        self, page_size: int = 1000
    ) -> AsyncGenerator[dict, None]:
        """分页流式读取 chunks，避免一次性全量加载到内存。

        适用于大量文档（>10万 chunks）场景，逐页 yield。
        """
        if page_size < 1:
            page_size = 1000

        if self._collection is not None:
            offset = 0
            while True:
                collection_results = self._collection.get(
                    include=["documents", "metadatas"],
                    limit=page_size,
                    offset=offset,
                )
                chunk_ids = collection_results.get("ids", [])
                if not chunk_ids:
                    break
                chunk_documents = collection_results.get("documents", [])
                chunk_metadatas = collection_results.get("metadatas", [])
                for chunk_index, chunk_id in enumerate(chunk_ids):
                    yield {
                        "chunk_id": chunk_id,
                        "content": chunk_documents[chunk_index] if chunk_index < len(chunk_documents) else "",
                        "metadata": chunk_metadatas[chunk_index] if chunk_index < len(chunk_metadatas) else {},
                    }
                offset += len(chunk_ids)
        else:
            for memory_item in self._memory_store:
                yield {
                    "chunk_id": memory_item["id"],
                    "content": memory_item["content"],
                    "metadata": memory_item["metadata"],
                }


def _safely_migrate_embedding_store(persist_dir: str):
    embedding_instance = get_embedding()
    version_file_path = os.path.join(persist_dir, ".embedding_version")
    current_version_tag = embedding_instance.version_tag

    existing_version_tag = "none"
    if os.path.exists(version_file_path):
        with open(version_file_path, "r", encoding="utf-8") as version_input_file:
            existing_version_tag = version_input_file.read().strip() or "none"

    if existing_version_tag == current_version_tag:
        return

    if os.path.isdir(persist_dir):
        for directory_name in os.listdir(persist_dir):
            if directory_name.startswith("migration_backup_"):
                continue
            current_path = os.path.join(persist_dir, directory_name)
            if os.path.basename(current_path) == ".embedding_version":
                continue
            if os.path.isdir(current_path):
                shutil.rmtree(current_path, ignore_errors=True)
            elif os.path.isfile(current_path):
                try:
                    os.remove(current_path)
                except OSError:
                    logger.warning("Failed to remove stale vector store file: %s", current_path)
    else:
        os.makedirs(persist_dir, exist_ok=True)

    logger.info(
        "Embedding backend changed from %s to %s. Cleared persisted vector store for full reindex.",
        existing_version_tag,
        current_version_tag,
    )
    with open(version_file_path, "w", encoding="utf-8") as version_output_file:
        version_output_file.write(current_version_tag)


vector_store = VectorStore()
