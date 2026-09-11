"""项目级业务异常定义。

service 层抛出的异常尽量放这里，api 层再映射为 HTTPException，
避免 service 层直接依赖 FastAPI。
"""


class UpstreamAPIError(Exception):
    """上游模型/API 返回的错误（如 API Key 无效、余额不足、参数错误等）。"""

    def __init__(
        self,
        status_code: int,
        detail: str,
        provider: str = "",
    ):
        super().__init__(detail)
        self.status_code = status_code
        self.detail = detail
        self.provider = provider
