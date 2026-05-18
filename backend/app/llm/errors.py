from __future__ import annotations


class LLMError(RuntimeError):
    def __init__(self, message: str, *, fallback_reason: str) -> None:
        super().__init__(message)
        self.fallback_reason = fallback_reason


class LLMConfigurationError(LLMError):
    """Raised when LLM runtime configuration is incomplete or invalid."""


class LLMProviderError(LLMError):
    """Raised when the compatible provider request fails."""


class LLMResponseError(LLMError):
    """Raised when the provider or assistant response cannot be used safely."""
