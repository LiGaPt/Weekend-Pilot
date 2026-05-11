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
    database_url: str = "postgresql://postgres:postgres@localhost:5432/weekend_pilot"
    redis_url: str = "redis://localhost:6379/0"
    langsmith_project: str = "weekend-pilot"
    langchain_tracing_v2: bool = False
    openai_api_key: SecretStr | None = None
    langsmith_api_key: SecretStr | None = None
    amap_maps_api_key: SecretStr | None = None
    baidu_map_api_key: SecretStr | None = None


@lru_cache
def get_settings() -> Settings:
    return Settings()
