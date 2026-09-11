import hashlib
import logging
from typing import List, Optional

import numpy as np

from app.config import EMBEDDING_CONFIG

logger = logging.getLogger(__name__)


class HashFallbackEmbedding:
    def __init__(self, dim: int = 384, ngram_range: tuple[int, int] = (1, 3), seed: int = 42):
        self.dim = dim
        self.ngram_range = ngram_range
        self._rng = np.random.RandomState(seed)
        self._projection_cache: dict[str, np.ndarray] = {}

    def _extract_ngrams(self, text: str) -> list[str]:
        normalized_text = text.lower().strip()
        extracted_ngrams: list[str] = []
        for ngram_length in range(self.ngram_range[0], self.ngram_range[1] + 1):
            for text_index in range(len(normalized_text) - ngram_length + 1):
                extracted_ngrams.append(normalized_text[text_index:text_index + ngram_length])
        for current_char in normalized_text:
            if current_char.strip():
                extracted_ngrams.append(current_char)
        return extracted_ngrams

    def _get_projection(self, ngram_text: str) -> np.ndarray:
        if ngram_text in self._projection_cache:
            return self._projection_cache[ngram_text]

        hash_value = int(hashlib.md5(ngram_text.encode("utf-8")).hexdigest(), 16)
        random_state = self._rng.get_state()
        self._rng.seed(hash_value % (2**31))
        projected_vector = self._rng.randn(self.dim).astype(np.float32)
        self._rng.set_state(random_state)
        self._projection_cache[ngram_text] = projected_vector
        return projected_vector

    def embed_single(self, text: str) -> list[float]:
        if not text or not text.strip():
            return [0.0] * self.dim

        extracted_ngrams = self._extract_ngrams(text)
        if not extracted_ngrams:
            return [0.0] * self.dim

        dense_vector = np.zeros(self.dim, dtype=np.float64)
        ngram_frequency: dict[str, int] = {}
        for ngram_text in extracted_ngrams:
            ngram_frequency[ngram_text] = ngram_frequency.get(ngram_text, 0) + 1

        total_ngrams = max(len(extracted_ngrams), 1)
        for ngram_text, ngram_count in ngram_frequency.items():
            term_frequency = ngram_count / total_ngrams
            projected_vector = self._get_projection(ngram_text)
            dense_vector += projected_vector * term_frequency

        vector_norm = np.linalg.norm(dense_vector)
        if vector_norm > 0:
            dense_vector = dense_vector / vector_norm

        return dense_vector.astype(np.float32).tolist()

    def embed(self, texts: list[str]) -> list[list[float]]:
        return [self.embed_single(current_text) for current_text in texts]

    @property
    def fitted(self) -> bool:
        return True

    @property
    def backend_name(self) -> str:
        return "hash_fallback"

    @property
    def model_name(self) -> str:
        return "hash-fallback-random-projection"

    @property
    def dimension(self) -> int:
        return self.dim

    @property
    def version_tag(self) -> str:
        return f"{self.backend_name}:{self.model_name}:{self.dimension}"


class SentenceTransformerEmbedding:
    def __init__(
        self,
        model_name: str,
        device_name: Optional[str],
        batch_size: int,
        normalize_embeddings: bool,
        cache_dir: Optional[str],
        fallback_dimension: int,
    ):
        self.model_name = model_name
        self.device_name = device_name
        self.batch_size = batch_size
        self.normalize_embeddings = normalize_embeddings
        self.cache_dir = cache_dir
        self.backend_name = "sentence_transformers"
        self._model = None
        self._dimension = fallback_dimension
        self._fallback_embedding = HashFallbackEmbedding(dim=fallback_dimension)
        self._load_model()

    def _load_model(self):
        try:
            from sentence_transformers import SentenceTransformer

            model_kwargs = {}
            if self.device_name and self.device_name != "auto":
                model_kwargs["device"] = self.device_name
            if self.cache_dir:
                model_kwargs["cache_folder"] = self.cache_dir

            self._model = SentenceTransformer(self.model_name, **model_kwargs)
            loaded_dimension = self._model.get_sentence_embedding_dimension()
            if isinstance(loaded_dimension, int) and loaded_dimension > 0:
                self._dimension = loaded_dimension

            logger.info(
                "SentenceTransformer embedding initialized: model=%s, dimension=%s, normalize=%s",
                self.model_name,
                self._dimension,
                self.normalize_embeddings,
            )
        except Exception as embedding_load_error:
            self._model = None
            logger.warning(
                "Failed to initialize SentenceTransformer embedding model %s: %s. Falling back to hash embedding.",
                self.model_name,
                embedding_load_error,
            )

    def embed(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []

        normalized_texts = [current_text if isinstance(current_text, str) else str(current_text) for current_text in texts]
        if self._model is None:
            return self._fallback_embedding.embed(normalized_texts)

        encoded_vectors = self._model.encode(
            normalized_texts,
            batch_size=self.batch_size,
            show_progress_bar=False,
            convert_to_numpy=True,
            normalize_embeddings=self.normalize_embeddings,
        )
        encoded_vectors = np.asarray(encoded_vectors, dtype=np.float32)
        return encoded_vectors.tolist()

    @property
    def fitted(self) -> bool:
        return self._model is not None

    @property
    def dimension(self) -> int:
        return self._dimension

    @property
    def version_tag(self) -> str:
        if self._model is None:
            return self._fallback_embedding.version_tag
        return f"{self.backend_name}:{self.model_name}:{self.dimension}"


_global_embedding: Optional[SentenceTransformerEmbedding] = None


def get_embedding() -> SentenceTransformerEmbedding:
    global _global_embedding
    if _global_embedding is None:
        init_embedding()
    return _global_embedding


def init_embedding(pipeline_dir: str = "", dim: int = 384):
    global _global_embedding
    embedding_model_name = EMBEDDING_CONFIG.get("model_name", "BAAI/bge-small-zh-v1.5")
    embedding_device_name = EMBEDDING_CONFIG.get("device", "auto")
    embedding_batch_size = int(EMBEDDING_CONFIG.get("batch_size", 32))
    embedding_normalize_flag = bool(EMBEDDING_CONFIG.get("normalize", True))
    embedding_cache_dir = EMBEDDING_CONFIG.get("cache_dir") or None
    fallback_dimension = int(EMBEDDING_CONFIG.get("fallback_dimension", dim))

    _global_embedding = SentenceTransformerEmbedding(
        model_name=embedding_model_name,
        device_name=embedding_device_name,
        batch_size=embedding_batch_size,
        normalize_embeddings=embedding_normalize_flag,
        cache_dir=embedding_cache_dir,
        fallback_dimension=fallback_dimension,
    )


async def fit_on_corpus(texts: list[str]):
    return None


async def get_embeddings_batch(texts: list[str]) -> list[list[float]]:
    return get_embedding().embed(texts)
