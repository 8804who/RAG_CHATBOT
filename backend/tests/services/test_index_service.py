import asyncio
from unittest.mock import AsyncMock

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
    log_repo.create_document_manage_log.assert_not_awaited()


def test_handle_success_marks_complete_with_success_log_on_last_chunk():
    # 마지막 청크(indexed == total)면 성공 이력을 남긴다.
    service, _, status_repo, log_repo = _make_service()
    status_repo.increment_indexed.return_value = (3, 3)  # 마지막 청크
    status_repo.get.return_value = None  # started_at은 현재 시각으로 대체

    asyncio.run(service.handle(AsyncMock(), _embedded_event()))

    log_repo.create_document_manage_log.assert_awaited_once()
    kwargs = log_repo.create_document_manage_log.await_args.kwargs
    assert kwargs["status"] == "success"
    assert kwargs["chunk_count"] == 3
    assert kwargs["document_id"] == "doc1"
