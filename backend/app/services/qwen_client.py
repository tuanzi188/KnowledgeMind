import logging

from app.config import QWEN_CONFIG, QWEN_MODEL_CONFIG
from app.services.openai_client import OpenAICompatibleClient

logger = logging.getLogger(__name__)


class QwenClient(OpenAICompatibleClient):
    """Qwen OpenAI 兼容客户端，仅保留配置差异。"""

    def __init__(self):
        super().__init__(
            config=QWEN_CONFIG,
            model_config=QWEN_MODEL_CONFIG,
            provider_name="Qwen",
            breaker_name="qwen_api",
        )


qwen_client = QwenClient()
