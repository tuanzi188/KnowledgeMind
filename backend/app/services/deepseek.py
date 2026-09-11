import logging

from app.config import DEEPSEEK_CONFIG, MODEL_CONFIG
from app.services.openai_client import OpenAICompatibleClient

logger = logging.getLogger(__name__)


class DeepSeekClient(OpenAICompatibleClient):
    """DeepSeek OpenAI 兼容客户端，仅保留配置差异。"""

    def __init__(self):
        super().__init__(
            config=DEEPSEEK_CONFIG,
            model_config=MODEL_CONFIG,
            provider_name="DeepSeek",
            breaker_name="deepseek_api",
        )


deepseek_client = DeepSeekClient()
