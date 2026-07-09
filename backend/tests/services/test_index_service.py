import asyncio
from unittest.mock import ANY, AsyncMock

from schemes.dto.document import RawPoint
from schemes.events import ChunkEmbeddedEvent
from services.ingestion.index_service import IndexService


def _make_service() -> tuple[IndexService, AsyncMock, AsyncMock, AsyncMock]:
    qdrant_repo = AsyncMock()
    status_repo = AsyncMock()
    log_repo = AsyncMock()
    service = IndexService(
        qdrant_repository=qdrant_repo,
        document_status_repository=status_repo,
        log_repository=log_repo,
    )
    return service, qdrant_repo, status_repo, log_repo


def _embedded_event() -> ChunkEmbeddedEvent:
    return ChunkEmbeddedEvent(
        document_id="doc1",
        collection_name="docs",
        filename="a.txt",
        chunk_id="c1",
        chunk_index=0,
        text="hello",
        total_chunks=3,
        created_at="2026-07-03T00:00:00+00:00",
        dense=[1.0, 2.0, 3.0],
        dense_vector_name="dense",
        sparse_indices=[1],
        sparse_values=[0.5],
        sparse_vector_name="sparse",
        embedding_model="BAAI/bge-m3",
        embedding_tokens=5,
    )


def test_handle_success_upserts_point_without_completion_log():
    # 청크를 upsert하고 진행도를 올리되, 아직 미완이면 성공 이력은 남기지 않는다.
    service, qdrant_repo, status_repo, log_repo = _make_service()
    status_repo.increment_indexed.return_value = (2, 3)  # 3개 중 2개 완료

    asyncio.run(service.handle(AsyncMock(), _embedded_event()))

    qdrant_repo.upsert_points.assert_awaited_once()
    collection, points = qdrant_repo.upsert_points.await_args.args
    assert collection == "docs"
    # 같은 chunk_id로 멱등 upsert (재처리에도 중복 없음).
    assert points[0].id == "c1"
    assert points[0].dense_vector_name == "dense"
    assert points[0].sparse is not None
    # 완료 시 다시 합산할 수 있도록 청크별 토큰을 payload에 실어 보낸다.
    assert points[0].payload["embedding_tokens"] == 5
    log_repo.create_document_manage_log.assert_not_awaited()
    qdrant_repo.scroll_points.assert_not_awaited()


def test_handle_success_marks_complete_with_success_log_on_last_chunk():
    # 마지막 청크(indexed == total)면 Qdrant에서 토큰 합을 다시 읽어 성공 이력을 남긴다.
    service, qdrant_repo, status_repo, log_repo = _make_service()
    status_repo.increment_indexed.return_value = (3, 3)  # 마지막 청크
    status_repo.get.return_value = None  # started_at은 현재 시각으로 대체
    log_repo.has_insert_success_log.return_value = False
    qdrant_repo.scroll_points.return_value = [
        RawPoint(id="c1", payload={"embedding_tokens": 5}),
        RawPoint(id="c2", payload={"embedding_tokens": 7}),
        RawPoint(id="c3", payload={}),  # 로컬 모델 등 누락 시 0으로 취급
    ]

    asyncio.run(service.handle(AsyncMock(), _embedded_event()))

    qdrant_repo.scroll_points.assert_awaited_once_with("docs", document_id="doc1")
    log_repo.create_document_manage_log.assert_awaited_once()
    kwargs = log_repo.create_document_manage_log.await_args.kwargs
    assert kwargs["status"] == "success"
    assert kwargs["chunk_count"] == 3
    assert kwargs["document_id"] == "doc1"
    # Qdrant payload에서 다시 읽어 합산한 임베딩 토큰과 모델명을 이력에 남긴다.
    assert kwargs["embedding_tokens"] == 12
    assert kwargs["embedding_model"] == "BAAI/bge-m3"


def test_handle_skips_success_log_when_already_logged():
    # 마지막 청크 이벤트가 재시도/재전송으로 중복 처리돼도 성공 이력은 1건만 남긴다.
    service, qdrant_repo, status_repo, log_repo = _make_service()
    status_repo.increment_indexed.return_value = (4, 3)  # 재처리로 total을 넘어선 경우
    log_repo.has_insert_success_log.return_value = True

    asyncio.run(service.handle(AsyncMock(), _embedded_event()))

    log_repo.has_insert_success_log.assert_awaited_once_with(ANY, "doc1")
    log_repo.create_document_manage_log.assert_not_awaited()
    qdrant_repo.scroll_points.assert_not_awaited()
