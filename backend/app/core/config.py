from pydantic_settings import BaseSettings, SettingsConfigDict


class Config(BaseSettings):
    # PostgreSQL
    POSTGRES_HOST: str
    POSTGRES_PORT: int
    POSTGRES_USER: str
    POSTGRES_PASSWORD: str
    POSTGRES_DB: str

    # Redis
    REDIS_HOST: str
    REDIS_PORT: int = 6379
    REDIS_PASSWORD: str
    REDIS_DB: int = 0

    # Qdrant
    QDRANT_URL: str
    QDRANT_API_KEY: str | None = None

    # OPENAI
    OPENAI_API_KEY: str | None = None

    # Kafka
    KAFKA_BOOTSTRAP_SERVERS: str = "localhost:9092"
    INGEST_MAX_RETRIES: int = 3

    # Google OAuth
    GOOGLE_CLIENT_ID: str
    GOOGLE_CLIENT_SECRET: str
    GOOGLE_REDIRECT_URI: str = "http://localhost:8000/api/v1/auth/google/callback"

    # Sessions
    SESSION_SECRET: str
    SESSION_COOKIE_NAME: str = "session"
    SESSION_TTL_SECONDS: int = 60 * 60 * 24 * 14  # 14 days
    SESSION_COOKIE_SECURE: bool = False  # set True behind HTTPS

    # Frontend
    FRONTEND_URL: str = "http://localhost:5173"

    model_config = SettingsConfigDict(
        env_file=".env",
        extra="ignore",
    )


config = Config()
