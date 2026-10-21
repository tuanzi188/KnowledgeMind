import os
import logging
from pathlib import Path
from typing import Any, Dict

from dotenv import load_dotenv
from app.core.secrets import secrets_manager

load_dotenv()

logger = logging.getLogger(__name__)

BASE_DIR = Path(__file__).resolve().parent.parent.parent
DATA_DIR = Path(os.getenv("DATA_DIR", str(BASE_DIR / "data"))).expanduser().resolve()
DATA_DIR.mkdir(parents=True, exist_ok=True)

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

EMBEDDING_CONFIG: Dict[str, Any] = {
    "model_name": os.getenv("EMBEDDING_MODEL_NAME", "BAAI/bge-small-zh-v1.5"),
    "device": os.getenv("EMBEDDING_DEVICE", "auto"),
    "batch_size": int(os.getenv("EMBEDDING_BATCH_SIZE", 32)),
    "normalize": os.getenv("EMBEDDING_NORMALIZE", "true").lower() == "true",
    "cache_dir": os.getenv("EMBEDDING_CACHE_DIR", ""),
    "fallback_dimension": int(os.getenv("EMBEDDING_FALLBACK_DIMENSION", 384)),
}

VECTOR_STORE_CONFIG: Dict[str, Any] = {
    "persist_dir": str(DATA_DIR / "chroma_db"),
    "collection_name": "knowledge_mind",
    "embedding_dimension": int(os.getenv("VECTOR_EMBEDDING_DIMENSION", 512)),
}

# L2 精排：优先调用托管重排（默认阿里云百炼 qwen3.7-text-rerank），
# 未配置 key、超时或接口异常时降级到本地 Cross-Encoder（BAAI/bge-reranker-base）。
RERANK_CONFIG: Dict[str, Any] = {
    "api_base_url": os.getenv(
        "RERANK_BASE_URL", "https://dashscope.aliyuncs.com/compatible-api/v1/reranks"
    ),
    "api_model": os.getenv("RERANK_MODEL", "qwen3.7-text-rerank"),
    "api_key": secrets_manager.get("RERANK_API_KEY") or secrets_manager.get("ALI_API_KEY"),
    "timeout_seconds": float(os.getenv("RERANK_TIMEOUT_SECONDS", "10")),
    "max_doc_chars": int(os.getenv("RERANK_MAX_DOC_CHARS", "600")),
}

RETRIEVAL_CONFIG: Dict[str, Any] = {
    "rrf_k": 60,
    # 查询改写默认关闭：当前改写对照实验存在候选池混淆（对照路用 25 候选、基线用 5 候选），
    # 结论不可复现，待重做同候选池 A/B 后再决定是否开启。
    "query_rewrite_enabled": os.getenv("QUERY_REWRITE_ENABLED", "false").lower() == "true",
    "rewrite_query_types": {"complex_analysis", "comparison"},
    "max_rewrite_queries": int(os.getenv("MAX_REWRITE_QUERIES", 3)),
    # l3（LLM 重排）只在实测有增益的查询类型上触发；关系推理零增益、文档摘要持平、
    # 精确查找/概念解释已饱和，均不应付出 1.5k token / 5.8s 的代价
    "l3_query_types": {"complex_analysis", "comparison"},
}

SERVER_CONFIG: Dict[str, Any] = {
    "cors_origins": os.getenv("CORS_ORIGINS", "http://localhost:5173,http://localhost:3000").split(","),
    "enable_fallback_chat": os.getenv("ENABLE_FALLBACK_CHAT", "false").lower() == "true",
    "bm25_rebuild_on_startup": os.getenv("BM25_REBUILD_ON_STARTUP", "true").lower() == "true",
}

CACHE_CONFIG: Dict[str, Any] = {
    "redis_url": os.getenv("REDIS_URL", "redis://localhost:6379/0"),
}

TOKENIZER_CONFIG: Dict[str, Any] = {
    "user_dict_path": os.getenv("TOKENIZER_USER_DICT_PATH", str(DATA_DIR / "tokenizer" / "user_dict.txt")),
    "enable_jieba": os.getenv("TOKENIZER_ENABLE_JIEBA", "true").lower() == "true",
}

_required_secrets = []
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
