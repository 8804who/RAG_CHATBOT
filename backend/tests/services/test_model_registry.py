import asyncio
from unittest.mock import AsyncMock

import pytest

from clients.embedding.embedding_client import EmbeddingClient
from exceptions.embedding import UnsupportedEmbeddingModelError
from schemes.dto.embedding import RegisteredEmbeddingModel
from services.model_registry import EmbeddingModelRegistry


def _make_registry() -> tuple[EmbeddingModelRegistry, EmbeddingClient]:
    """단일 모델을 가진 레지스트리 생성 헬퍼."""
    client = AsyncMock(spec=EmbeddingClient)
    info = RegisteredEmbeddingModel(
        name="BAAI/bge-m3", provider="fastembed", dimension=1024
    )
    registry = EmbeddingModelRegistry(catalog={"BAAI/bge-m3": (info, client)})
    return registry, client


def test_list_models_success_with_registered_models():
    # 카탈로그에 등록된 모델 메타 목록을 반환한다.
    registry, _ = _make_registry()

    models = registry.list_models()

    assert len(models) == 1
    assert models[0].name == "BAAI/bge-m3"
    assert models[0].dimension == 1024


def test_resolve_success_with_registered_model():
    # 등록된 모델 이름으로 해당 client를 resolve한다.
    registry, client = _make_registry()

    resolved = registry.resolve("BAAI/bge-m3")

    assert resolved is client


def test_resolve_failed_with_unknown_model():
    # 미등록 모델은 UnsupportedEmbeddingModelError를 발생시킨다.
    registry, _ = _make_registry()

    with pytest.raises(UnsupportedEmbeddingModelError):
        registry.resolve("unknown-model")


def test_get_info_failed_with_unknown_model():
    # 미등록 모델 메타 조회도 예외를 발생시킨다.
    registry, _ = _make_registry()

    with pytest.raises(UnsupportedEmbeddingModelError):
        registry.get_info("unknown-model")


def test_warmup_success_with_all_clients():
    # 등록된 모든 client의 warmup을 호출해 선로딩한다.
    client_a = AsyncMock(spec=EmbeddingClient)
    client_b = AsyncMock(spec=EmbeddingClient)
    info_a = RegisteredEmbeddingModel(name="a", provider="p", dimension=1)
    info_b = RegisteredEmbeddingModel(name="b", provider="p", dimension=1)
    registry = EmbeddingModelRegistry(
        catalog={"a": (info_a, client_a), "b": (info_b, client_b)}
    )

    asyncio.run(registry.warmup())

    client_a.warmup.assert_awaited_once()
    client_b.warmup.assert_awaited_once()


def test_warmup_success_with_one_client_failing():
    # 한 provider의 warmup 실패가 전파되지 않고 나머지는 계속 로드된다.
    failing = AsyncMock(spec=EmbeddingClient)
    failing.warmup.side_effect = RuntimeError("missing api key")
    healthy = AsyncMock(spec=EmbeddingClient)
    info_f = RegisteredEmbeddingModel(name="f", provider="openai", dimension=1)
    info_h = RegisteredEmbeddingModel(name="h", provider="fastembed", dimension=1)
    registry = EmbeddingModelRegistry(
        catalog={"f": (info_f, failing), "h": (info_h, healthy)}
    )

    # 예외가 전파되지 않아야 한다(시작 차단 방지).
    asyncio.run(registry.warmup())

    failing.warmup.assert_awaited_once()
    healthy.warmup.assert_awaited_once()
