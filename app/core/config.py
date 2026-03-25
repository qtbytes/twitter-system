from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "FastAPI Twitter System"
    database_url: str = "sqlite:///./twitter.db"
    redis_url: str = "redis://localhost:6379/0"

    timeline_cache_ttl_seconds: int = 30
    default_timeline_strategy: str = "read"
    timeline_page_size: int = 20

    rq_queue_name: str = "feed-fanout"
    rq_job_timeout_seconds: int = 600
    run_fanout_inline_when_queue_unavailable: bool = True

    rate_limit_enabled: bool = True
    rate_limit_post_tweet_max_requests: int = 10
    rate_limit_post_tweet_window_seconds: int = 60
    rate_limit_like_max_requests: int = 60
    rate_limit_like_window_seconds: int = 60
    rate_limit_comment_max_requests: int = 30
    rate_limit_comment_window_seconds: int = 60
    rate_limit_timeline_max_requests: int = 120
    rate_limit_timeline_window_seconds: int = 60

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


settings = Settings()
