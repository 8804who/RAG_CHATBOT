from unittest.mock import AsyncMock

import pytest

from langchain_core.language_models import BaseChatModel

from clients.embedding.embedding_client import EmbeddingClient
from exceptions.chat import UnsupportedChatModelError
from exceptions.embedding import UnsupportedEmbeddingModelError
from schemes.dto.chat import RegisteredChatModel
from schemes.dto.embedding import RegisteredEmbeddingModel
from services.model_registry import ChatModelRegistry, EmbeddingModelRegistry


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


def _make_chat_registry() -> tuple[ChatModelRegistry, BaseChatModel]:
    """단일 채팅 모델을 가진 레지스트리 생성 헬퍼."""
    client = AsyncMock(spec=BaseChatModel)
    info = RegisteredChatModel(name="gpt-4o-mini", provider="openai")
    registry = ChatModelRegistry(catalog={"gpt-4o-mini": (info, client)})
    return registry, client


def test_chat_registry_list_models_success_with_registered_models():
    # 카탈로그에 등록된 채팅 모델 메타 목록을 반환한다.
    registry, _ = _make_chat_registry()

    models = registry.list_models()

    assert len(models) == 1
    assert models[0].name == "gpt-4o-mini"
    assert models[0].provider == "openai"


def test_chat_registry_resolve_success_with_registered_model():
    # 등록된 모델 이름으로 해당 client를 resolve한다.
    registry, client = _make_chat_registry()

    resolved = registry.resolve("gpt-4o-mini")

    assert resolved is client


def test_chat_registry_resolve_failed_with_unknown_model():
    # 미등록 모델은 UnsupportedChatModelError를 발생시킨다.
    registry, _ = _make_chat_registry()

    with pytest.raises(UnsupportedChatModelError):
        registry.resolve("unknown-model")


def test_chat_registry_get_info_failed_with_unknown_model():
    # 미등록 모델 메타 조회도 예외를 발생시킨다.
    registry, _ = _make_chat_registry()

    with pytest.raises(UnsupportedChatModelError):
        registry.get_info("unknown-model")
