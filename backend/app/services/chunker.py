import re
import uuid
import math
import hashlib
from typing import List, Optional
from dataclasses import dataclass

from app.models.chat import DocumentChunk, ChunkingStrategy


class FixedChunker:
    """固定分块: 按字符数切分，重叠20%"""

    def __init__(self, chunk_size: int = 512, chunk_overlap: float = 0.2):
        self.chunk_size = chunk_size
        self.overlap_size = int(chunk_size * chunk_overlap)

    def split(self, text: str) -> list[str]:
        if not text or not text.strip():
            return []
        step = max(self.chunk_size - self.overlap_size, 1)
        chunks = []
        for i in range(0, len(text), step):
            chunk = text[i:i + self.chunk_size].strip()
            if chunk:
                chunks.append(chunk)
        return chunks


class SemanticChunker:
    """语义分块: 基于Embedding相似度动态切分"""

    def __init__(self, chunk_size: int = 512, similarity_threshold: float = 0.6):
        self.chunk_size = chunk_size
        self.similarity_threshold = similarity_threshold
        self.separators = ["\n\n", "\n", "。", ".", "！", "？", "；", "，", " "]

    def split(self, text: str, embeddings_fn=None) -> list[str]:
        if not text or not text.strip():
            return []
        sentences = self._split_sentences(text)
        if len(sentences) <= 1:
            return [text.strip()] if text.strip() else []
        return self._merge_sentences(sentences, embeddings_fn)

    def _split_sentences(self, text: str) -> list[str]:
        sentences = re.split(r'(?<=[。！？.!?])\s*', text)
        return [s.strip() for s in sentences if s.strip()]

    def _merge_sentences(self, sentences: list[str], embeddings_fn) -> list[str]:
        if embeddings_fn is None:
            return self._merge_by_size(sentences)
        try:
            embeddings = embeddings_fn(sentences)
            return self._merge_by_similarity(sentences, embeddings)
        except Exception:
            return self._merge_by_size(sentences)

    def _merge_by_similarity(self, sentences: list[str], embeddings: list) -> list[str]:
        import numpy as np
        embeddings = np.array(embeddings, dtype=np.float32)
        norms = np.linalg.norm(embeddings, axis=1, keepdims=True) + 1e-10
        embeddings = embeddings / norms

        chunks = []
        current_chunk = [sentences[0]]
        current_emb = embeddings[0]

        for i in range(1, len(sentences)):
            similarity = float(np.dot(current_emb, embeddings[i]))
            if similarity >= self.similarity_threshold and len("".join(current_chunk)) + len(sentences[i]) <= self.chunk_size:
                current_chunk.append(sentences[i])
                current_emb = (current_emb * len(current_chunk) + embeddings[i]) / (len(current_chunk) + 1)
            else:
                chunks.append("".join(current_chunk))
                current_chunk = [sentences[i]]
                current_emb = embeddings[i]

        if current_chunk:
            chunks.append("".join(current_chunk))
        return chunks

    def _merge_by_size(self, sentences: list[str]) -> list[str]:
        chunks = []
        current = ""
        for s in sentences:
            if len(current) + len(s) <= self.chunk_size:
                current += s
            else:
                if current:
                    chunks.append(current)
                current = s
        if current:
            chunks.append(current)
        return chunks


class StructuralChunker:
    """结构分块: 基于文档层级结构（标题/段落/表格）"""

    def __init__(self, max_chunk_size: int = 1024):
        self.max_chunk_size = max_chunk_size

    def split(self, text: str) -> list[str]:
        if not text or not text.strip():
            return []

        sections = self._detect_structure(text)
        chunks = []
        for section in sections:
            if len(section) <= self.max_chunk_size:
                chunks.append(section)
            else:
                sub_chunks = self._split_long_section(section)
                chunks.extend(sub_chunks)
        return chunks

    def _detect_structure(self, text: str) -> list[str]:
        lines = text.split("\n")
        sections = []
        current = ""
        heading_pattern = re.compile(
            r'^(#{1,6}\s+|第[一二三四五六七八九十\d]+[章节部分篇]|'
            r'\d+[\.、．\)]\s*|[一二三四五六七八九十]+[、．]\s*|'
            r'=== |--- |\*\*\*|【.+?】)'
        )

        for line in lines:
            stripped = line.strip()
            if not stripped:
                if current:
                    current += "\n"
                continue

            if heading_pattern.match(stripped) or (
                current and len(stripped) < 30 and not any(p in stripped for p in "，。！？.")
                and len(current.split("\n")) > 1
            ):
                if current.strip():
                    sections.append(current.strip())
                current = line + "\n"
                continue

            table_line = re.match(r'^\|.+\|$', stripped) or re.match(r'^[\+\-]+$', stripped)
            if table_line:
                current += line + "\n"
                continue

            current += line + "\n"

        if current.strip():
            sections.append(current.strip())

        if len(sections) == 0 and text.strip():
            return [text.strip()]
        if len(sections) == 1:
            return sections

        return sections

    def _split_long_section(self, section: str) -> list[str]:
        paragraphs = re.split(r'\n\s*\n', section)
        chunks = []
        current = ""
        for p in paragraphs:
            if len(current) + len(p) <= self.max_chunk_size:
                current += ("\n\n" + p) if current else p
            else:
                if current:
                    chunks.append(current)
                if len(p) > self.max_chunk_size:
                    step = self.max_chunk_size // 2
                    for i in range(0, len(p), step):
                        sub = p[i:i + self.max_chunk_size].strip()
                        if sub:
                            chunks.append(sub)
                else:
                    current = p
        if current:
            chunks.append(current)
        return chunks if chunks else [section]


class ChunkingPipeline:
    def __init__(self, default_strategy: ChunkingStrategy = ChunkingStrategy.semantic):
        self.default_strategy = default_strategy
        self.fixed_chunker = FixedChunker(chunk_size=512, chunk_overlap=0.2)
        self.semantic_chunker = SemanticChunker(chunk_size=512, similarity_threshold=0.6)
        self.structural_chunker = StructuralChunker(max_chunk_size=1024)

    def create_chunks(
        self,
        document_id: str,
        content: str,
        metadata: dict,
        strategy: Optional[ChunkingStrategy] = None,
        embeddings_fn=None,
    ) -> List[DocumentChunk]:
        strategy = strategy or self.default_strategy

        if strategy == ChunkingStrategy.fixed:
            texts = self.fixed_chunker.split(content)
        elif strategy == ChunkingStrategy.semantic:
            texts = self.semantic_chunker.split(content, embeddings_fn)
        elif strategy == ChunkingStrategy.structural:
            texts = self.structural_chunker.split(content)
        else:
            texts = self.fixed_chunker.split(content)

        chunks = []
        for i, text in enumerate(texts):
            if not text.strip():
                continue
            # 使用内容哈希生成稳定且不重复的 chunk_id，避免同一文档重新上传时 ID 冲突
            chunk_hash = hashlib.sha256(f"{document_id}:{i}:{text}".encode("utf-8")).hexdigest()[:16]
            chunks.append(DocumentChunk(
                chunk_id=f"{document_id}_chunk_{chunk_hash}",
                doc_id=document_id,
                content=text,
                metadata={
                    **metadata,
                    "chunk_index": i,
                    "total_chunks": len(texts),
                    "chunk_strategy": strategy.value,
                    "char_count": len(text),
                },
            ))
        return chunks