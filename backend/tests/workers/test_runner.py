import asyncio
from types import SimpleNamespace
from unittest.mock import ANY, AsyncMock

from core.config import config
from schemes.events import DocumentUploadedEvent
from workers.runner import _process_message


def _message(event: DocumentUploadedEvent) -> SimpleNamespace:
    return SimpleNamespace(
        key=event.document_id.encode(),
        value=event.to_bytes(),
        topic="documents.uploaded",
    )


def _uploaded_event(**overrides: object) -> DocumentUploadedEvent:
    fields = {
        "document_id": "doc1",
        "collection_name": "docs",
        "filename": "a.txt",
        "content": "hello",
        "requester_id": 7,
        "requester_email": "a@b.com",
    }
    fields.update(overrides)
    return DocumentUploadedEvent(**fields)


def test_process_message_logs_failure_after_retries_exhausted(monkeypatch):
    # 재시도 소진 시 문서를 FAILED로 표시할 뿐 아니라 감사 이력(document_manage_logs)에도
    # 실패를 남긴다. 이전에는 성공만 기록되고 실패는 이력에서 완전히 빠졌었다.
    monkeypatch.setattr(config, "INGEST_MAX_RETRIES", 1)
    monkeypatch.setattr("workers.runner._send_to_dlq", AsyncMock())
    status_repo = AsyncMock()
    status_repo.get.return_value = None  # started_at은 현재 시각으로 대체
    log_repo = AsyncMock()
    handler = AsyncMock(side_effect=RuntimeError("boom"))

    asyncio.run(
        _process_message(
            _message(_uploaded_event()),
            stage="parsing",
            event_type=DocumentUploadedEvent,
            handler=handler,
            status_repository=status_repo,
            log_repository=log_repo,
        )
    )

    status_repo.set_failed.assert_awaited_once_with(ANY, "doc1", "boom")
    log_repo.create_document_manage_log.assert_awaited_once()
    kwargs = log_repo.create_document_manage_log.await_args.kwargs
    assert kwargs["status"] == "failed"
    assert kwargs["document_id"] == "doc1"
    assert kwargs["collection_name"] == "docs"
    assert kwargs["requester_id"] == 7


def test_process_message_success_skips_failure_handling(monkeypatch):
    # 정상 처리되면 FAILED 표시도, 실패 이력도 남기지 않는다.
    monkeypatch.setattr(config, "INGEST_MAX_RETRIES", 3)
    monkeypatch.setattr("workers.runner._send_to_dlq", AsyncMock())
    status_repo = AsyncMock()
    log_repo = AsyncMock()
    handler = AsyncMock(return_value=None)

    asyncio.run(
        _process_message(
            _message(_uploaded_event()),
            stage="parsing",
            event_type=DocumentUploadedEvent,
            handler=handler,
            status_repository=status_repo,
            log_repository=log_repo,
        )
    )

    status_repo.set_failed.assert_not_awaited()
    log_repo.create_document_manage_log.assert_not_awaited()
