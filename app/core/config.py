from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "FastAPI Twitter System"
    database_url: str = "sqlite:///./twitter.db"
    redis_url: str = "redis://localhost:6379/0"
    timeline_cache_ttl_seconds: int = 30
    default_timeline_strategy: str = "read"
    timeline_page_size: int = 20

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


settings = Settings()
