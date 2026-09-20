import logging
import os
from typing import List, Optional


class SecretsManager:
    """只从环境读取配置，源码中不保存凭据。"""

    def get(self, key: str, default: Optional[str] = None) -> Optional[str]:
        return os.getenv(key, default)

    def is_configured(self, key: str) -> bool:
        value = self.get(key)
        return bool(value and value.strip() and value != f"your_{key.lower()}_here")

    def get_required(self, key: str) -> str:
        if not self.is_configured(key):
            raise RuntimeError(f"缺少必要配置：{key}")
        return self.get(key).strip()

    def validate_required_secrets(self, required_keys: List[str]) -> List[str]:
        missing_keys = [key for key in required_keys if not self.is_configured(key)]
        if missing_keys:
            logging.getLogger(__name__).warning("缺少必要配置：%s", ", ".join(missing_keys))
        return missing_keys


secrets_manager = SecretsManager()
