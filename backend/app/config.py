import os
import logging
from pathlib import Path
from typing import Any, Dict

from dotenv import load_dotenv
from app.core.secrets import secrets_manager

load_dotenv()

logger = logging.getLogger(__name__)

BASE_DIR = Path(__file__).resolve().parent.parent.parent
DATA_DIR = BASE_DIR.parent / "data"
DATA_DIR.mkdir(parents=True, exist_ok=True)

MODEL_MODE = os.getenv("MODEL_MODE", "api")

# 模型提供商选择: deepseek / qwen
MODEL_PROVIDER = os.getenv("MODEL_PROVIDER", "deepseek").strip().lower()

API_KEY = secrets_manager.get("API_KEY", "")

MAX_UPLOAD_SIZE_MB = int(os.getenv("MAX_UPLOAD_SIZE_MB", "50"))
MAX_UPLOAD_SIZE_BYTES = MAX_UPLOAD_SIZE_MB * 1024 * 1024

DEEPSEEK_CONFIG: Dict[str, Dict[str, Any]] = {
    "primary": {
        "base_url": os.getenv("DS_BASE_URL", "https://api.deepseek.com/v1"),
        "api_key": secrets_manager.get("DS_API_KEY"),
    },
    "fallback_1": {
        "base_url": os.getenv("ALI_BASE_URL", "https://dashscope.aliyuncs.com/compatible-mode/v1"),
        "api_key": secrets_manager.get("ALI_API_KEY"),
    },
}

QWEN_CONFIG: Dict[str, Dict[str, Any]] = {
    "primary": {
        "base_url": os.getenv("QWEN_BASE_URL", "https://dashscope.aliyuncs.com/compatible-mode/v1"),
        "api_key": secrets_manager.get("QWEN_API_KEY"),
    },
    "fallback_1": {
        "base_url": os.getenv("DS_BASE_URL", "https://api.deepseek.com/v1"),
        "api_key": secrets_manager.get("DS_API_KEY"),
    },
}

MODEL_CONFIG: Dict[str, Any] = {
    "flash": {
        "model": os.getenv("FLASH_MODEL", "deepseek-chat"),
        "max_tokens": 2048,
        "temperature": 0.1,
    },
    "pro": {
        "model": os.getenv("PRO_MODEL", "deepseek-reasoner"),
        "max_tokens": 4096,
        "temperature": 0.1,
    },
}

QWEN_MODEL_CONFIG: Dict[str, Any] = {
    "flash": {
        "model": os.getenv("QWEN_FLASH_MODEL", "qwen-turbo"),
        "max_tokens": 2048,
        "temperature": 0.1,
    },
    "pro": {
        "model": os.getenv("QWEN_PRO_MODEL", "qwen-plus"),
        "max_tokens": 4096,
        "temperature": 0.1,
    },
}

OLLAMA_CONFIG: Dict[str, Any] = {
    "base_url": os.getenv("OLLAMA_BASE_URL", "http://127.0.0.1:11434/v1"),
    "chat_model": os.getenv("OLLAMA_CHAT_MODEL", "qwen2.5:7b-instruct"),
    "embedding_model": os.getenv("OLLAMA_EMBEDDING_MODEL", "nomic-embed-text"),
    "max_tokens": int(os.getenv("OLLAMA_MAX_TOKENS", 4096)),
    "temperature": float(os.getenv("OLLAMA_TEMPERATURE", 0.1)),
}

EMBEDDING_CONFIG: Dict[str, Any] = {
    "provider": os.getenv("EMBEDDING_PROVIDER", "sentence_transformers"),
    "model_name": os.getenv("EMBEDDING_MODEL_NAME", "BAAI/bge-small-zh-v1.5"),
    "device": os.getenv("EMBEDDING_DEVICE", "auto"),
    "batch_size": int(os.getenv("EMBEDDING_BATCH_SIZE", 32)),
    "normalize": os.getenv("EMBEDDING_NORMALIZE", "true").lower() == "true",
    "cache_dir": os.getenv("EMBEDDING_CACHE_DIR", ""),
    "fallback_dimension": int(os.getenv("EMBEDDING_FALLBACK_DIMENSION", 384)),
}

VECTOR_STORE_CONFIG: Dict[str, Any] = {
    "type": os.getenv("VECTOR_STORE_TYPE", "chroma"),
    "persist_dir": str(DATA_DIR / "chroma_db"),
    "collection_name": "knowledge_mind",
    "embedding_dimension": int(os.getenv("VECTOR_EMBEDDING_DIMENSION", 512)),
}

RETRIEVAL_CONFIG: Dict[str, Any] = {
    "top_k_retrieval": 10,
    "top_k_rerank": 5,
    "rrf_k": 60,
    "similarity_threshold": 0.6,
    "query_rewrite_enabled": os.getenv("QUERY_REWRITE_ENABLED", "true").lower() == "true",
    "max_rewrite_queries": int(os.getenv("MAX_REWRITE_QUERIES", 3)),
}

SERVER_CONFIG: Dict[str, Any] = {
    "host": os.getenv("HOST", "0.0.0.0"),
    "port": int(os.getenv("PORT", 8002)),
    "reload": os.getenv("RELOAD", "true").lower() == "true",
    "cors_origins": os.getenv("CORS_ORIGINS", "http://localhost:5173,http://localhost:3000").split(","),
    "enable_fallback_chat": os.getenv("ENABLE_FALLBACK_CHAT", "false").lower() == "true",
    "bm25_rebuild_on_startup": os.getenv("BM25_REBUILD_ON_STARTUP", "true").lower() == "true",
}

CACHE_CONFIG: Dict[str, Any] = {
    "l1_ttl_seconds": 60,
    "l2_ttl_seconds": 3600,
    "redis_url": os.getenv("REDIS_URL", "redis://localhost:6379/0"),
    "max_lru_size": 1000,
}

# Harness 韧性工程配置
RESILIENCE_CONFIG: Dict[str, Any] = {
    "circuit_breaker": {
        "enabled": os.getenv("CB_ENABLED", "true").lower() == "true",
        "failure_threshold": int(os.getenv("CB_FAILURE_THRESHOLD", "5")),
        "recovery_timeout": float(os.getenv("CB_RECOVERY_TIMEOUT", "30")),
    },
    "retry": {
        "enabled": os.getenv("RETRY_ENABLED", "true").lower() == "true",
        "max_retries": int(os.getenv("RETRY_MAX_RETRIES", "3")),
        "base_delay": float(os.getenv("RETRY_BASE_DELAY", "0.5")),
        "max_delay": float(os.getenv("RETRY_MAX_DELAY", "30")),
    },
    "graceful_degradation": {
        "enabled": os.getenv("GRACEFUL_DEGRADATION_ENABLED", "true").lower() == "true",
    },
}

TOKENIZER_CONFIG: Dict[str, Any] = {
    "user_dict_path": os.getenv("TOKENIZER_USER_DICT_PATH", str(DATA_DIR / "tokenizer" / "user_dict.txt")),
    "enable_jieba": os.getenv("TOKENIZER_ENABLE_JIEBA", "true").lower() == "true",
}

_required_secrets = []
if MODEL_MODE == "api":
    if MODEL_PROVIDER == "qwen":
        _required_secrets.append("QWEN_API_KEY")
    else:
        _required_secrets.append("DS_API_KEY")
missing = secrets_manager.validate_required_secrets(_required_secrets)
if missing:
    logger.warning(
        "Missing required API keys: %s. The application may not function correctly.",
        ", ".join(missing),
    )