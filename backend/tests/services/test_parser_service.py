import asyncio
from unittest.mock import AsyncMock

import pytest

from exceptions.document import EmptyDocumentError
from schemes.dto.qdrant import CollectionDetail, DenseVectorDetail, SparseVectorDetail
from schemes.events import TOPIC_DOCUMENTS_PARSED, DocumentParsedEvent, DocumentUploadedEvent
from services.ingestion.parser_service import ParserService

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


def _make_service() -> tuple[ParserService, AsyncMock, AsyncMock, AsyncMock, AsyncMock]:
    qdrant_repo = AsyncMock()
    meta_repo = AsyncMock()
    status_repo = AsyncMock()
    kafka_producer = AsyncMock()
    service = ParserService(
        qdrant_repository=qdrant_repo,
        collection_meta_repository=meta_repo,
        document_status_repository=status_repo,
        kafka_producer=kafka_producer,
    )
    return service, qdrant_repo, meta_repo, status_repo, kafka_producer


def _uploaded_event(content: str = "hello world") -> DocumentUploadedEvent:
    return DocumentUploadedEvent(
        document_id="doc1",
        collection_name="docs",
        filename="a.txt",
        content=content,
    )


def test_handle_success_with_publish_per_chunk():
    # 청크마다 documents.parsed를 발행하고 총 청크 수를 기록한다.
    service, qdrant_repo, meta_repo, status_repo, kafka_producer = _make_service()
    meta_repo.get_collection_metadata.return_value = type(
        "Meta", (), {"embedding_model": MODEL}
    )()
    qdrant_repo.get_collection.return_value = _collection_detail(with_sparse=True)

    asyncio.run(service.handle(AsyncMock(), _uploaded_event()))

    # 단일 청크 입력 → 총 1개, 발행 1회.
    status_repo.set_total_chunks.assert_awaited_once()
    assert status_repo.set_total_chunks.await_args.args[2] == 1
    kafka_producer.publish.assert_awaited_once()
    assert kafka_producer.publish.await_args.args[0] == TOPIC_DOCUMENTS_PARSED

    # 컬렉션 고정 모델·벡터 이름이 다음 단계로 전달된다.
    parsed = DocumentParsedEvent.from_bytes(
        kafka_producer.publish.await_args.kwargs["value"]
    )
    assert parsed.embedding_model == MODEL
    assert parsed.dense_vector_name == "dense"
    assert parsed.sparse_vector_name == "sparse"
    assert parsed.with_sparse is True
    assert parsed.total_chunks == 1


def test_handle_failed_with_empty_content():
    # 청크가 생성되지 않는 빈 내용은 EmptyDocumentError를 발생시킨다(→ 워커가 DLQ).
    service, qdrant_repo, meta_repo, _, kafka_producer = _make_service()
    meta_repo.get_collection_metadata.return_value = type(
        "Meta", (), {"embedding_model": MODEL}
    )()
    qdrant_repo.get_collection.return_value = _collection_detail()

    with pytest.raises(EmptyDocumentError):
        asyncio.run(service.handle(AsyncMock(), _uploaded_event("   ")))
    kafka_producer.publish.assert_not_awaited()
