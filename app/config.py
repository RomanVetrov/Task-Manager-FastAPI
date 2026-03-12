from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    DATABASE_URL: str
    SECRET_KEY: str
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 10
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7
    REDIS_URL: str = "redis://localhost:6379/0"
    TASKS_LIST_CACHE_TTL_SECONDS: int = 60
    # Argon2 tuning (can be overridden via .env)
    ARGON_TIME_COST: int = 3
    ARGON_MEMORY_COST: int = 65536  # KiB (≈64 MiB)
    ARGON_PARALLELISM: int = 2
    ARGON_HASH_LEN: int = 32
    ARGON_SALT_LEN: int = 16
    ARGON_MAX_PASSWORD_LEN: int = 1024  # basic DoS guard
    OTEL_ENABLED: bool = True
    OTEL_SERVICE_NAME: str = "task-manager-api"
    OTEL_EXPORTER_OTLP_ENDPOINT: str = "http://localhost:4317"
    OTEL_EXPORTER_OTLP_INSECURE: bool = True
    OTEL_SAMPLE_RATIO: float = 1.0

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


settings = Settings()
