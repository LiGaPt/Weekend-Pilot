from functools import lru_cache

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = "WeekendPilot"
    app_env: str = "local"
    app_version: str = "0.1.0"
    log_level: str = "INFO"
    database_url: str = "postgresql+psycopg://postgres:postgres@localhost:5432/weekend_pilot"
    redis_url: str = "redis://localhost:6379/0"
    langsmith_project: str = "weekend-pilot"
    langsmith_tracing: bool = False
    langsmith_endpoint: str | None = None
    local_trace_buffer_path: str = "var/traces/weekendpilot-traces.jsonl"
    demo_cors_origins: list[str] = [
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:5174",
        "http://127.0.0.1:5174",
    ]
    langchain_tracing_v2: bool = False
    llm_enabled: bool = False
    llm_api_key: SecretStr | None = None
    llm_base_url: str | None = None
    llm_model_id: str | None = None
    llm_timeout: float = 10.0
    openai_api_key: SecretStr | None = None
    langsmith_api_key: SecretStr | None = None
    amap_maps_api_key: SecretStr | None = None
    baidu_map_api_key: SecretStr | None = None


@lru_cache
def get_settings() -> Settings:
    return Settings()
