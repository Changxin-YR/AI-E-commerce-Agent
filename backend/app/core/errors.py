class BusinessError(Exception):
    """An expected failure safe to expose through the API."""

    def __init__(self, code: str, message: str, status_code: int = 400) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.status_code = status_code


class NotFoundError(BusinessError):
    def __init__(self, message: str = "记录不存在或当前账号无权访问") -> None:
        super().__init__("not_found", message, 404)


class ConflictError(BusinessError):
    def __init__(self, message: str) -> None:
        super().__init__("conflict", message, 409)


class AuthenticationError(BusinessError):
    def __init__(self, message: str = "请先登录") -> None:
        super().__init__("authentication_required", message, 401)
