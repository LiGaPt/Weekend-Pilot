from typing import Any


class ToolGatewayError(Exception):
    code: str

    def __init__(self, code: str, message: str) -> None:
        self.code = code
        super().__init__(message)


def error_json(
    code: str,
    message: str,
    details: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "code": code,
        "message": message,
        "details": details or {},
    }
