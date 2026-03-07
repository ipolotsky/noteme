from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="NOTEME_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Telegram Bot
    bot_token: str
    bot_username: str = ""

    # Database (PostgreSQL)
    db_host: str = "localhost"
    db_port: int = 5433
    db_name: str = "noteme"
    db_user: str = "noteme"
    db_password: str

    # Redis
    redis_host: str = "localhost"
    redis_port: int = 6380
    redis_db: int = 0
    redis_password: str | None = None

    # OpenAI
    openai_api_key: str = ""
    openai_model: str = "gpt-4o-mini"
    openai_whisper_model: str = "whisper-1"

    # Admin Panel
    admin_username: str = "admin"
    admin_password: str = "admin"
    admin_secret_key: str = "change-me-in-production"

    # Sentry
    sentry_dsn: str = ""
    sentry_environment: str = "development"

    # App
    app_host: str = "0.0.0.0"
    app_port: int = 8000
    app_debug: bool = False
    app_domain: str = ""
    app_base_url: str = ""

    # Default User Limits (future monetization)
    default_max_events: int = 10
    default_max_wishes: int = 10
    default_max_people_per_entity: int = 3

    # AI Rate Limits
    ai_rate_limit_per_minute: int = 30
    ai_rate_limit_per_hour: int = 200

    # Notifications
    default_notification_time: str = "09:00"
    default_weekly_digest_time: str = "19:00"
    default_weekly_digest_day: int = 6

    # Logging
    log_level: str = "INFO"
    log_format: str = "text"

    @model_validator(mode="after")
    def _set_base_url_default(self) -> "Settings":
        if not self.app_base_url:
            if self.app_domain:
                self.app_base_url = f"https://{self.app_domain}"
            else:
                self.app_base_url = f"http://localhost:{self.app_port}"
        return self

    @property
    def database_url(self) -> str:
        from urllib.parse import quote_plus
        return (
            f"postgresql+asyncpg://{quote_plus(self.db_user)}:{quote_plus(self.db_password)}"
            f"@{self.db_host}:{self.db_port}/{self.db_name}"
        )

    @property
    def database_url_sync(self) -> str:
        from urllib.parse import quote_plus
        return (
            f"postgresql://{quote_plus(self.db_user)}:{quote_plus(self.db_password)}"
            f"@{self.db_host}:{self.db_port}/{self.db_name}"
        )

    @property
    def redis_url(self) -> str:
        auth = f":{self.redis_password}@" if self.redis_password else ""
        return f"redis://{auth}{self.redis_host}:{self.redis_port}/{self.redis_db}"


settings = Settings()  # type: ignore[call-arg]
