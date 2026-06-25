import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from exceptions.vector_db import (
    CollectionAlreadyExistsError,
    CollectionNotFoundError,
)
from qdrant_client import models
from repositories.vector_db import QdrantRepository
from schemes.dto.qdrant import (
    CollectionDetail,
    CollectionSummary,
    DenseVectorDetail,
    SparseVectorDetail,
)
from schemes.requests import (
    CreateQdrantCollectionRequest,
    DenseVectorUpdateConfig,
    UpdateQdrantCollectionRequest,
)


def _make_repository() -> tuple[QdrantRepository, AsyncMock]:
    """AsyncMock client를 가진 QdrantRepository 생성 헬퍼."""
    fake_client = AsyncMock()
    db_client = type("FakeQdrantDBClient", (), {"client": fake_client})()
    return QdrantRepository(qdrant_client=db_client), fake_client


def _create_request() -> CreateQdrantCollectionRequest:
    return CreateQdrantCollectionRequest(
        collection_name="docs",
        dense_vectors={"dense": {"size": 1024, "distance": "Cosine", "on_disk": False}},
        sparse_vectors={},
        embedding_model={"name": "BAAI/bge-m3", "dimension": 1024, "normalize": True},
        on_disk_payload=True,
    )


def test_get_collections_success_with_named_collections():
    # client 응답의 collections를 CollectionSummary DTO 목록으로 변환한다.
    repo, client = _make_repository()
    client.get_collections.return_value = SimpleNamespace(
        collections=[SimpleNamespace(name="docs"), SimpleNamespace(name="faq")]
    )

    result = asyncio.run(repo.get_collections())

    assert result == [CollectionSummary(name="docs"), CollectionSummary(name="faq")]


def test_get_collection_success_with_enum_normalization():
    # enum(status/distance/modifier)이 .value 문자열로 정규화되어 DTO로 매핑된다.
    repo, client = _make_repository()
    client.collection_exists.return_value = True
    client.get_collection.return_value = SimpleNamespace(
        status=models.CollectionStatus.GREEN,
        points_count=42,
        config=SimpleNamespace(
            params=SimpleNamespace(
                vectors={
                    "dense": models.VectorParams(
                        size=1024,
                        distance=models.Distance.COSINE,
                        on_disk=True,
                    )
                },
                sparse_vectors={
                    "sparse": models.SparseVectorParams(
                        modifier=models.Modifier.IDF,
                        index=models.SparseIndexParams(on_disk=True),
                    )
                },
            ),
            optimizer_config=SimpleNamespace(
                indexing_threshold=20000,
                default_segment_number=2,
            ),
        ),
    )

    result = asyncio.run(repo.get_collection("docs"))

    assert result == CollectionDetail(
        name="docs",
        status="green",
        points_count=42,
        dense_vectors={
            "dense": DenseVectorDetail(size=1024, distance="Cosine", on_disk=True)
        },
        sparse_vectors={"sparse": SparseVectorDetail(modifier="idf", on_disk=True)},
        indexing_threshold=20000,
        default_segment_number=2,
    )


def test_delete_collection_success_with_existing_collection():
    # 존재하는 collection 삭제 시 client.delete_collection이 호출되고 True 반환
    repo, client = _make_repository()
    client.collection_exists.return_value = True
    client.delete_collection.return_value = True

    result = asyncio.run(repo.delete_collection("docs"))

    assert result is True
    client.delete_collection.assert_awaited_once_with(collection_name="docs")


def test_delete_collection_failed_with_missing_collection():
    # 존재하지 않는 collection 삭제 시 CollectionNotFoundError 발생
    repo, client = _make_repository()
    client.collection_exists.return_value = False

    with pytest.raises(CollectionNotFoundError):
        asyncio.run(repo.delete_collection("missing"))

    client.delete_collection.assert_not_awaited()


def test_create_collections_failed_with_duplicate_name():
    # 이미 존재하는 이름으로 생성 시 CollectionAlreadyExistsError 발생
    repo, client = _make_repository()
    client.collection_exists.return_value = True

    with pytest.raises(CollectionAlreadyExistsError):
        asyncio.run(repo.create_collections(_create_request()))

    client.create_collection.assert_not_awaited()


def test_update_collection_success_with_dense_on_disk():
    # dense vector on_disk 변경 시 VectorParamsDiff로 변환되어 전달
    repo, client = _make_repository()
    client.collection_exists.return_value = True
    client.update_collection.return_value = True

    request = UpdateQdrantCollectionRequest(
        dense_vectors={"dense": DenseVectorUpdateConfig(on_disk=True)}
    )
    result = asyncio.run(repo.update_collection("docs", request))

    assert result is True
    _, kwargs = client.update_collection.call_args
    assert kwargs["collection_name"] == "docs"
    assert kwargs["vectors_config"]["dense"] == models.VectorParamsDiff(on_disk=True)


def test_update_collection_failed_with_missing_collection():
    # 존재하지 않는 collection 수정 시 CollectionNotFoundError 발생
    repo, client = _make_repository()
    client.collection_exists.return_value = False

    request = UpdateQdrantCollectionRequest(
        dense_vectors={"dense": DenseVectorUpdateConfig(on_disk=True)}
    )
    with pytest.raises(CollectionNotFoundError):
        asyncio.run(repo.update_collection("missing", request))

    client.update_collection.assert_not_awaited()
