import asyncio
from unittest.mock import AsyncMock

from clients.embedding.embedding_client import EmbeddingClient
from clients.embedding.sparse_encoder import SparseEncoder
from schemes.dto.embedding import RegisteredEmbeddingModel, SparseVector
from services.embedding.embedding_service import EmbeddingService
from services.model_registry import EmbeddingModelRegistry

MODEL = "BAAI/bge-m3"


def _make_service(
    dense_client: AsyncMock, sparse_encoder: AsyncMock
) -> EmbeddingService:
    """가짜 dense client·sparse encoder로 EmbeddingService 생성 헬퍼."""
    info = RegisteredEmbeddingModel(name=MODEL, provider="fastembed", dimension=3)
    registry = EmbeddingModelRegistry(catalog={MODEL: (info, dense_client)})
    return EmbeddingService(embedding_registry=registry, sparse_encoder=sparse_encoder)


def test_embed_documents_success_with_sparse():
    # dense는 resolve된 모델로, sparse는 공통 인코더로 생성해 결합한다.
    dense_client = AsyncMock(spec=EmbeddingClient)
    dense_client.embed_documents.return_value = [[1.0, 2.0, 3.0], [4.0, 5.0, 6.0]]
    sparse_encoder = AsyncMock(spec=SparseEncoder)
    sparse_encoder.encode_documents.return_value = [
        SparseVector(indices=[1], values=[1.0]),
        SparseVector(indices=[2], values=[2.0]),
    ]
    service = _make_service(dense_client, sparse_encoder)

    result = asyncio.run(service.embed_documents(MODEL, ["a", "b"]))

    assert len(result) == 2
    assert result[0].dense == [1.0, 2.0, 3.0]
    assert result[0].sparse.indices == [1]
    dense_client.embed_documents.assert_awaited_once_with(["a", "b"])


def test_embed_documents_success_with_sparse_disabled():
    # with_sparse=False면 sparse 인코더를 호출하지 않고 sparse는 None이다.
    dense_client = AsyncMock(spec=EmbeddingClient)
    dense_client.embed_documents.return_value = [[1.0, 2.0, 3.0]]
    sparse_encoder = AsyncMock(spec=SparseEncoder)
    service = _make_service(dense_client, sparse_encoder)

    result = asyncio.run(service.embed_documents(MODEL, ["a"], with_sparse=False))

    assert result[0].sparse is None
    sparse_encoder.encode_documents.assert_not_awaited()


def test_embed_documents_success_with_empty_input():
    # 빈 입력은 provider 호출 없이 빈 결과를 반환한다.
    dense_client = AsyncMock(spec=EmbeddingClient)
    sparse_encoder = AsyncMock(spec=SparseEncoder)
    service = _make_service(dense_client, sparse_encoder)

    result = asyncio.run(service.embed_documents(MODEL, []))

    assert result == []
    dense_client.embed_documents.assert_not_awaited()


def test_embed_query_success_with_sparse():
    # 질의 임베딩도 dense + sparse를 결합해 반환한다.
    dense_client = AsyncMock(spec=EmbeddingClient)
    dense_client.embed_query.return_value = [0.1, 0.2, 0.3]
    sparse_encoder = AsyncMock(spec=SparseEncoder)
    sparse_encoder.encode_query.return_value = SparseVector(indices=[5], values=[1.0])
    service = _make_service(dense_client, sparse_encoder)

    result = asyncio.run(service.embed_query(MODEL, "질문"))

    assert result.dense == [0.1, 0.2, 0.3]
    assert result.sparse.indices == [5]
