from fastapi.testclient import TestClient

from main import app


def test_metrics_success_with_prior_request():
    """
    Prometheus 메트릭 노출(성공)

    입력 데이터
        - GET /health 1회 호출 후 GET /metrics

    예상 출력 데이터
        - 200 응답, http_request 계열 메트릭과 /health 라우트 템플릿 라벨 포함
        - /metrics 자체는 계측 대상에서 제외
    """
    # lifespan(Postgres/Kafka 연결)을 띄우지 않도록 컨텍스트 매니저 없이 사용한다.
    client = TestClient(app)
    client.get("/health")

    response = client.get("/metrics")

    assert response.status_code == 200
    assert "http_requests_total" in response.text
    assert "http_request_duration_seconds" in response.text
    assert 'handler="/health"' in response.text
    assert 'handler="/metrics"' not in response.text


def _lifespan_mocks() -> dict:
    """lifespan이 여는 외부 자원(DB 시딩·Qdrant·Redis·Kafka·체크포인터) 대역."""
    from unittest.mock import AsyncMock, MagicMock

    checkpointer = MagicMock()
    checkpointer.conn.open = AsyncMock()
    checkpointer.conn.close = AsyncMock()
    checkpointer.setup = AsyncMock()
    return {
        "qdrant": AsyncMock(),
        "redis": AsyncMock(),
        "kafka": AsyncMock(),
        "checkpointer": checkpointer,
    }


def _run_lifespan(mocks: dict) -> None:
    import asyncio
    from contextlib import asynccontextmanager
    from unittest.mock import AsyncMock, MagicMock, patch

    import main

    @asynccontextmanager
    async def fake_session():
        yield AsyncMock()

    async def run() -> None:
        async with main.lifespan(app):
            pass

    with (
        patch.object(main, "AsyncSessionLocal", fake_session),
        patch.object(main, "get_pricing_repository", return_value=AsyncMock()),
        patch.object(main, "get_qdrant_client", return_value=mocks["qdrant"]),
        patch.object(main, "get_redis_client", return_value=mocks["redis"]),
        patch.object(main, "get_kafka_producer", return_value=mocks["kafka"]),
        patch.object(main, "get_checkpointer", return_value=mocks["checkpointer"]),
        patch.object(main, "get_embedding_registry", MagicMock()),
        patch.object(main, "get_chat_model_registry", MagicMock()),
        patch.object(main, "get_sparse_encoder", MagicMock()),
        patch.object(main, "get_langfuse_handler", MagicMock()),
        patch.object(main, "ensure_topics", AsyncMock()),
    ):
        asyncio.run(run())


def test_lifespan_success_with_all_resources_closed():
    """
    앱 lifespan(성공) - 정상 기동·종료 시 모든 자원 정리

    입력 데이터
        - 모든 외부 자원 정상

    예상 출력 데이터
        - 체크포인터 풀·Qdrant·Redis·Kafka 모두 close 1회
    """
    mocks = _lifespan_mocks()

    _run_lifespan(mocks)

    mocks["checkpointer"].conn.close.assert_awaited_once()
    mocks["qdrant"].close.assert_awaited_once()
    mocks["redis"].close.assert_awaited_once()
    mocks["kafka"].close.assert_awaited_once()


def test_lifespan_failed_with_checkpointer_setup_error():
    """
    앱 lifespan(실패) - Kafka 시작 이후 체크포인터 setup 실패(CR-014 F6)

    입력 데이터
        - checkpointer.setup()이 RuntimeError

    예상 출력 데이터
        - RuntimeError 전파, 이미 연 풀·Qdrant·Redis·Kafka는 모두 close
    """
    import pytest

    mocks = _lifespan_mocks()
    mocks["checkpointer"].setup.side_effect = RuntimeError("db down")

    with pytest.raises(RuntimeError):
        _run_lifespan(mocks)

    mocks["checkpointer"].conn.close.assert_awaited_once()
    mocks["qdrant"].close.assert_awaited_once()
    mocks["redis"].close.assert_awaited_once()
    mocks["kafka"].close.assert_awaited_once()


def test_lifespan_failed_with_one_close_error():
    """
    앱 lifespan(실패) - 종료 중 한 자원 close 실패해도 나머지는 정리

    입력 데이터
        - checkpointer 풀 close가 RuntimeError

    예상 출력 데이터
        - RuntimeError 전파, Qdrant·Redis·Kafka는 close
    """
    import pytest

    mocks = _lifespan_mocks()
    mocks["checkpointer"].conn.close.side_effect = RuntimeError("close failed")

    with pytest.raises(RuntimeError):
        _run_lifespan(mocks)

    mocks["qdrant"].close.assert_awaited_once()
    mocks["redis"].close.assert_awaited_once()
    mocks["kafka"].close.assert_awaited_once()
