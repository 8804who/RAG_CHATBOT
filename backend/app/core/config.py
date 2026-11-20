import os

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

    # FastEmbed(dense/sparse 로컬 모델) 캐시 경로
    FASTEMBED_CACHE_PATH: str | None = None

    # 에이전트 웹 검색 도구(langchain-tavily). 미설정 시 웹 검색 도구를 생략한다.
    TAVILY_API_KEY: str | None = None

    # Langfuse(에이전트 실행 추적). 둘 다 설정된 경우에만 추적을 활성화한다.
    LANGFUSE_PUBLIC_KEY: str | None = None
    LANGFUSE_SECRET_KEY: str | None = None
    LANGFUSE_BASE_URL: str | None = None

    # Logging
    LOG_LEVEL: str = "INFO"
    # 헬스체크·메트릭 스크레이프 등 인프라 경로(/health, /metrics, /)의 로그 출력 여부.
    # 기본 False: 주기적 스크레이프가 API 호출 로그·uvicorn access 로그를 덮지 않게 한다.
    LOG_INFRA_ENDPOINTS: bool = False

    model_config = SettingsConfigDict(
        env_file=".env",
        extra="ignore",
    )


config = Config()

if config.FASTEMBED_CACHE_PATH:
    os.environ.setdefault("FASTEMBED_CACHE_PATH", config.FASTEMBED_CACHE_PATH)

# langchain-tavily/langfuse SDK는 생성자 인자가 아니라 환경변수를 직접 읽으므로,
# Config에 실려 온 값을 동일한 이름의 환경변수로 다시 노출해야 한다.
if config.TAVILY_API_KEY:
    os.environ.setdefault("TAVILY_API_KEY", config.TAVILY_API_KEY)
if config.LANGFUSE_PUBLIC_KEY:
    os.environ.setdefault("LANGFUSE_PUBLIC_KEY", config.LANGFUSE_PUBLIC_KEY)
if config.LANGFUSE_SECRET_KEY:
    os.environ.setdefault("LANGFUSE_SECRET_KEY", config.LANGFUSE_SECRET_KEY)
if config.LANGFUSE_BASE_URL:
    os.environ.setdefault("LANGFUSE_BASE_URL", config.LANGFUSE_BASE_URL)
