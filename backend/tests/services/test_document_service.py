import asyncio
from unittest.mock import AsyncMock

import pytest

from exceptions.document import CollectionMetaNotFoundError, EmptyDocumentError
from schemes.dto.document import RawPoint
from schemes.dto.embedding import EmbeddingResult, SparseVector
from schemes.dto.qdrant import CollectionDetail, DenseVectorDetail, SparseVectorDetail
from services.ingestion.document_service import DocumentService

MODEL = "BAAI/bge-m3"


def _collection_detail(with_sparse: bool = True) -> CollectionDetail:
    """dense(+sparse) vector 이름을 가진 CollectionDetail 헬퍼."""
    return CollectionDetail(
        name="docs",
        status="green",
        points_count=0,
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


def _make_service() -> tuple[DocumentService, AsyncMock, AsyncMock, AsyncMock]:
    """가짜 repo/embedding_service/meta_repo로 DocumentService 생성 헬퍼."""
    qdrant_repo = AsyncMock()
    embedding_service = AsyncMock()
    meta_repo = AsyncMock()
    service = DocumentService(
        qdrant_repository=qdrant_repo,
        embedding_service=embedding_service,
        collection_meta_repository=meta_repo,
    )
    return service, qdrant_repo, embedding_service, meta_repo


def test_ingest_success_with_sparse_collection():
    # 메타의 임베딩 모델로 청크를 임베딩하고 dense+sparse 포인트를 upsert한다.
    service, qdrant_repo, embedding_service, meta_repo = _make_service()
    meta_repo.get.return_value = type(
        "Meta", (), {"embedding_model": MODEL, "dimension": 3}
    )()
    qdrant_repo.get_collection.return_value = _collection_detail(with_sparse=True)
    embedding_service.embed_documents.return_value = [
        EmbeddingResult(dense=[1.0, 2.0, 3.0], sparse=SparseVector([1], [1.0])),
    ]

    result = asyncio.run(service.ingest(AsyncMock(), "docs", "a.txt", "hello world"))

    assert result.filename == "a.txt"
    assert result.chunk_count == 1
    embedding_service.embed_documents.assert_awaited_once()
    # 컬렉션에 고정된 모델 이름이 임베딩에 전달돼야 한다.
    assert embedding_service.embed_documents.await_args.args[0] == MODEL
    qdrant_repo.upsert_points.assert_awaited_once()
    points = qdrant_repo.upsert_points.await_args.args[1]
    assert len(points) == 1
    assert points[0].dense_vector_name == "dense"
    assert points[0].sparse_vector_name == "sparse"
    assert points[0].payload["document_id"] == result.document_id


def test_ingest_failed_with_missing_meta():
    # 임베딩 모델 매핑이 없으면 CollectionMetaNotFoundError를 발생시킨다.
    service, _, _, meta_repo = _make_service()
    meta_repo.get.return_value = None

    with pytest.raises(CollectionMetaNotFoundError):
        asyncio.run(service.ingest(AsyncMock(), "docs", "a.txt", "hello"))


def test_ingest_failed_with_empty_content():
    # 청크가 생성되지 않는 빈 내용은 EmptyDocumentError를 발생시킨다.
    service, qdrant_repo, _, meta_repo = _make_service()
    meta_repo.get.return_value = type("Meta", (), {"embedding_model": MODEL})()
    qdrant_repo.get_collection.return_value = _collection_detail()

    with pytest.raises(EmptyDocumentError):
        asyncio.run(service.ingest(AsyncMock(), "docs", "a.txt", "   "))


def test_list_documents_success_with_grouping():
    # 같은 document_id의 청크는 하나의 문서로 묶이고 chunk_count가 합산된다.
    service, qdrant_repo, _, _ = _make_service()
    qdrant_repo.scroll_points.return_value = [
        RawPoint(
            id="p1",
            payload={
                "document_id": "doc1",
                "filename": "a.txt",
                "created_at": "2026-06-20T00:00:00",
            },
        ),
        RawPoint(
            id="p2",
            payload={
                "document_id": "doc1",
                "filename": "a.txt",
                "created_at": "2026-06-20T00:00:00",
            },
        ),
        RawPoint(
            id="p3",
            payload={
                "document_id": "doc2",
                "filename": "b.txt",
                "created_at": "2026-06-21T00:00:00",
            },
        ),
    ]

    result = asyncio.run(service.list_documents("docs"))

    assert len(result) == 2
    # created_at 최신순 정렬: doc2가 먼저.
    assert result[0].document_id == "doc2"
    doc1 = next(d for d in result if d.document_id == "doc1")
    assert doc1.chunk_count == 2


def test_get_document_chunks_success_with_index_sort():
    # 청크는 chunk_index 오름차순으로 정렬돼 반환된다.
    service, qdrant_repo, _, _ = _make_service()
    qdrant_repo.scroll_points.return_value = [
        RawPoint(id="p2", payload={"chunk_index": 1, "text": "second"}),
        RawPoint(id="p1", payload={"chunk_index": 0, "text": "first"}),
    ]

    result = asyncio.run(service.get_document_chunks("docs", "doc1"))

    assert [c.chunk_index for c in result] == [0, 1]
    assert result[0].text == "first"
