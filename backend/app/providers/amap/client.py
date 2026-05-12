from __future__ import annotations

from typing import Any

import httpx

from backend.app.providers.amap.errors import AMapConfigurationError, AMapProviderError


class AMapClient:
    def __init__(
        self,
        api_key: str,
        base_url: str = "https://restapi.amap.com",
        timeout_seconds: float = 5.0,
        http_client: httpx.Client | None = None,
    ) -> None:
        if not api_key or not api_key.strip():
            raise AMapConfigurationError("AMAP API key is not configured.")

        self._api_key = api_key
        self._http_client = http_client or httpx.Client(
            base_url=base_url,
            timeout=timeout_seconds,
        )

    def get(self, path: str, params: dict[str, Any]) -> dict[str, Any]:
        request_params = {**params, "key": self._api_key}
        try:
            response = self._http_client.get(path, params=request_params)
            response.raise_for_status()
        except httpx.TimeoutException as exc:
            raise AMapProviderError("AMAP request timed out.") from exc
        except httpx.HTTPError as exc:
            raise AMapProviderError("AMAP HTTP request failed.") from exc

        try:
            payload = response.json()
        except ValueError as exc:
            raise AMapProviderError("AMAP response was not valid JSON.") from exc

        if not isinstance(payload, dict):
            raise AMapProviderError("AMAP response JSON was not an object.")

        status = payload.get("status")
        if status is not None and status != "1":
            infocode = payload.get("infocode", "unknown")
            info = payload.get("info", "AMAP request failed")
            raise AMapProviderError(f"AMAP request failed: {infocode} {info}")

        return payload
