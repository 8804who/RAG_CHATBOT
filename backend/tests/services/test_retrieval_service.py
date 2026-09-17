import asyncio
from unittest.mock import AsyncMock

import pytest

from exceptions.document import (
    CollectionMetaNotFoundError,
    DenseVectorNotConfiguredError,
)
from models import CollectionMeta
from schemes.dto.embedding import EmbeddingResult, SparseVector
from schemes.dto.qdrant import CollectionDetail, DenseVectorDetail, SparseVectorDetail
from schemes.dto.retrieval import RetrievedPoint
from services.retrieval.retrieval_service import RetrievalService


def _make_service(qdrant_repository, collection_meta_repository, embedding_service):
    return RetrievalService(
        qdrant_repository=qdrant_repository,
        collection_meta_repository=collection_meta_repository,
        embedding_service=embedding_service,
    )


def _collection_detail(with_sparse: bool) -> CollectionDetail:
    return CollectionDetail(
        name="docs",
        status="green",
        points_count=10,
        dense_vectors={
            "dense": DenseVectorDetail(size=3, distance="Cosine", on_disk=False)
        },
        sparse_vectors=(
            {"sparse": SparseVectorDetail(modifier="idf", on_disk=False)}
            if with_sparse
            else {}
        ),
        indexing_threshold=None,
        default_segment_number=None,
    )


def test_retrieve_success_with_hybrid_search():
    # 컬렉션에 dense+sparse가 모두 있으면 하이브리드 검색을 수행한다.
    qdrant_repository = AsyncMock()
    qdrant_repository.get_collection.return_value = _collection_detail(with_sparse=True)
    qdrant_repository.search.return_value = [
        RetrievedPoint(
            id="c1",
            score=0.8,
            payload={
                "document_id": "d1",
                "filename": "a.txt",
                "chunk_index": 0,
                "text": "hello",
            },
        )
    ]
    collection_meta_repository = AsyncMock()
    collection_meta_repository.get_collection_metadata.return_value = CollectionMeta(
        collection_name="docs", embedding_model="BAAI/bge-m3", dimension=3
    )
    embedding_service = AsyncMock()
    embedding_service.embed_query.return_value = EmbeddingResult(
        dense=[0.1, 0.2, 0.3], sparse=SparseVector(indices=[1], values=[1.0])
    )
    service = _make_service(
        qdrant_repository, collection_meta_repository, embedding_service
    )

    result = asyncio.run(service.retrieve(AsyncMock(), "docs", "질문"))

    assert len(result) == 1
    assert result[0].chunk_id == "c1"
    assert result[0].document_id == "d1"
    embedding_service.embed_query.assert_awaited_once_with(
        "BAAI/bge-m3", "질문", with_sparse=True
    )
    _, kwargs = qdrant_repository.search.call_args
    assert kwargs["sparse_vector_name"] == "sparse"


def test_retrieve_success_with_dense_only_fallback():
    # sparse vector가 컬렉션에 없으면 dense 단독으로 검색한다.
    qdrant_repository = AsyncMock()
    qdrant_repository.get_collection.return_value = _collection_detail(
        with_sparse=False
    )
    qdrant_repository.search.return_value = []
    collection_meta_repository = AsyncMock()
    collection_meta_repository.get_collection_metadata.return_value = CollectionMeta(
        collection_name="docs", embedding_model="BAAI/bge-m3", dimension=3
    )
    embedding_service = AsyncMock()
    embedding_service.embed_query.return_value = EmbeddingResult(
        dense=[0.1, 0.2, 0.3], sparse=None
    )
    service = _make_service(
        qdrant_repository, collection_meta_repository, embedding_service
    )

    asyncio.run(service.retrieve(AsyncMock(), "docs", "질문"))

    embedding_service.embed_query.assert_awaited_once_with(
        "BAAI/bge-m3", "질문", with_sparse=False
    )
    _, kwargs = qdrant_repository.search.call_args
    assert kwargs["sparse_vector_name"] is None


def test_retrieve_failed_with_missing_collection_meta():
    # 컬렉션에 임베딩 모델 매핑이 없으면 CollectionMetaNotFoundError
    qdrant_repository = AsyncMock()
    collection_meta_repository = AsyncMock()
    collection_meta_repository.get_collection_metadata.return_value = None
    embedding_service = AsyncMock()
    service = _make_service(
        qdrant_repository, collection_meta_repository, embedding_service
    )

    with pytest.raises(CollectionMetaNotFoundError):
        asyncio.run(service.retrieve(AsyncMock(), "docs", "질문"))

    qdrant_repository.get_collection.assert_not_awaited()


def test_retrieve_failed_with_no_dense_vector_configured():
    # 컬렉션에 dense vector가 구성되어 있지 않으면 DenseVectorNotConfiguredError
    qdrant_repository = AsyncMock()
    qdrant_repository.get_collection.return_value = CollectionDetail(
        name="docs",
        status="green",
        points_count=0,
        dense_vectors={},
        sparse_vectors={},
        indexing_threshold=None,
        default_segment_number=None,
    )
    collection_meta_repository = AsyncMock()
    collection_meta_repository.get_collection_metadata.return_value = CollectionMeta(
        collection_name="docs", embedding_model="BAAI/bge-m3", dimension=3
    )
    embedding_service = AsyncMock()
    service = _make_service(
        qdrant_repository, collection_meta_repository, embedding_service
    )

    with pytest.raises(DenseVectorNotConfiguredError):
        asyncio.run(service.retrieve(AsyncMock(), "docs", "질문"))

    embedding_service.embed_query.assert_not_awaited()
