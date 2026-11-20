FROM ghcr.io/astral-sh/uv:python3.13-bookworm-slim

# 런타임에 __pycache__ 를 쓸 수 없으므로(읽기 전용 앱 파일) 빌드 시 바이트코드를 미리 컴파일한다.
# UV_COMPILE_BYTECODE 는 의존성만, 아래 compileall 은 앱 코드를 컴파일한다.
ENV UV_COMPILE_BYTECODE=1

WORKDIR /app

COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-install-project

COPY . .
RUN uv sync --frozen
RUN python -m compileall -q /app

# 비root 실행: 앱 파일은 root 소유·읽기 전용으로 두고, 쓰기 경로는 fastembed 캐시만 앱 사용자에게 준다.
RUN useradd --uid 10001 --create-home app \
    && mkdir -p /cache/fastembed \
    && chown app:app /cache/fastembed

ENV PATH="/app/.venv/bin:${PATH}"
USER 10001
