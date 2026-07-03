import asyncio
from unittest.mock import AsyncMock

from schemes.dto.document import RawPoint
from schemes.events import TOPIC_DOCUMENTS_UPLOADED, DocumentUploadedEvent
from services.ingestion.document_service import DocumentService


def _make_service() -> tuple[DocumentService, AsyncMock, AsyncMock, AsyncMock, AsyncMock]:
    """가짜 repo/producer/status_repo/log_repo로 DocumentService 생성 헬퍼."""
    qdrant_repo = AsyncMock()
    kafka_producer = AsyncMock()
    status_repo = AsyncMock()
    log_repo = AsyncMock()
    service = DocumentService(
        qdrant_repository=qdrant_repo,
        kafka_producer=kafka_producer,
        document_status_repository=status_repo,
        log_repository=log_repo,
    )
    return service, qdrant_repo, kafka_producer, status_repo, log_repo


def test_accept_upload_success_with_publish_and_record():
    # 상태 레코드를 UPLOADED로 생성하고 documents.uploaded에 원문을 발행한다.
    service, _, kafka_producer, status_repo, _ = _make_service()

    result = asyncio.run(
        service.accept_upload(
            AsyncMock(),
            "docs",
            "a.txt",
            "hello world",
            requester_id=7,
            requester_email="u@e.com",
        )
    )

    # 상태 레코드 생성이 호출됐고, document_id가 이벤트/레코드로 일관되게 흐른다.
    status_repo.create.assert_awaited_once()
    document_id = status_repo.create.await_args.kwargs["document_id"]

    kafka_producer.publish.assert_awaited_once()
    topic = kafka_producer.publish.await_args.args[0]
    assert topic == TOPIC_DOCUMENTS_UPLOADED
    assert kafka_producer.publish.await_args.kwargs["key"] == document_id

    # 발행된 payload가 업로드 이벤트로 역직렬화되고 원문·요청자를 담는다.
    value = kafka_producer.publish.await_args.kwargs["value"]
    event = DocumentUploadedEvent.from_bytes(value)
    assert event.document_id == document_id
    assert event.collection_name == "docs"
    assert event.content == "hello world"
    assert event.requester_id == 7
    # accept_upload는 임베딩을 하지 않고 상태 레코드를 반환한다.
    assert result is status_repo.create.return_value


def test_delete_document_success_with_audit_log():
    # Qdrant 청크와 상태 레코드를 지우고 성공 이력을 남긴다.
    service, qdrant_repo, _, status_repo, log_repo = _make_service()

    asyncio.run(
        service.delete_document(
            AsyncMock(), "docs", "doc1", requester_id=1, requester_email="u@e.com"
        )
    )

    qdrant_repo.delete_by_document.assert_awaited_once_with("docs", "doc1")
    status_repo.delete.assert_awaited_once()
    log_repo.create_document_manage_log.assert_awaited_once()
    assert log_repo.create_document_manage_log.await_args.kwargs["status"] == "success"


def test_list_documents_success_with_grouping():
    # 같은 document_id의 청크는 하나의 문서로 묶이고 chunk_count가 합산된다.
    service, qdrant_repo, _, _, _ = _make_service()
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
    service, qdrant_repo, _, _, _ = _make_service()
    qdrant_repo.scroll_points.return_value = [
        RawPoint(id="p2", payload={"chunk_index": 1, "text": "second"}),
        RawPoint(id="p1", payload={"chunk_index": 0, "text": "first"}),
    ]

    result = asyncio.run(service.get_document_chunks("docs", "doc1"))

    assert [c.chunk_index for c in result] == [0, 1]
    assert result[0].text == "first"
