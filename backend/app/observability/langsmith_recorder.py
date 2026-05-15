from __future__ import annotations

from typing import Any

from pydantic import SecretStr

from backend.app.observability.schemas import LangSmithPostStatus


class LangSmithRecorder:
    def __init__(
        self,
        *,
        enabled: bool,
        api_key: SecretStr | str | None,
        project_name: str,
        endpoint: str | None = None,
        strict: bool = False,
    ) -> None:
        self.enabled = enabled
        self.api_key = api_key
        self.project_name = project_name
        self.endpoint = endpoint
        self.strict = strict

    def post_summary(self, payload: dict[str, Any]) -> LangSmithPostStatus:
        if not self.enabled:
            return LangSmithPostStatus(enabled=False, posted=False)
        if not self.api_key:
            return LangSmithPostStatus(enabled=True, posted=False)

        try:
            from langsmith import Client

            api_key = (
                self.api_key.get_secret_value()
                if isinstance(self.api_key, SecretStr)
                else self.api_key
            )
            client = Client(api_key=api_key, api_url=self.endpoint)
            client.create_run(
                name="weekendpilot_run_summary",
                run_type="chain",
                project_name=self.project_name,
                inputs={"run_id": payload.get("run_id")},
                outputs=payload,
                extra={"metadata": payload.get("metadata") or {}},
            )
        except Exception as exc:
            if self.strict:
                raise
            return LangSmithPostStatus(
                enabled=True,
                posted=False,
                error=f"{type(exc).__name__}: {exc}",
            )

        return LangSmithPostStatus(enabled=True, posted=True)
