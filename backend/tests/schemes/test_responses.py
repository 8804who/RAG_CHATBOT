from datetime import datetime, timedelta, timezone

from schemes.responses import DocumentStatusResponse


def _make_response(
    *,
    status: str = "EMBEDDING",
    total_chunks: int | None = 10,
    indexed_chunks: int = 0,
    embedding_started_at: datetime | None = None,
) -> DocumentStatusResponse:
    return DocumentStatusResponse(
        document_id="doc1",
        status=status,
        filename="a.txt",
        total_chunks=total_chunks,
        indexed_chunks=indexed_chunks,
        embedding_started_at=embedding_started_at,
    )


def test_progress_percent_success_with_no_total_chunks():
    # 청킹이 끝나 total_chunks가 확정되기 전(UPLOADED)에는 0%.
    response = _make_response(status="UPLOADED", total_chunks=None, indexed_chunks=0)

    assert response.progress_percent == 0.0


def test_progress_percent_success_with_partial_progress():
    # indexed_chunks/total_chunks 비율을 %로 반환한다.
    response = _make_response(total_chunks=10, indexed_chunks=5)

    assert response.progress_percent == 50.0


def test_progress_percent_success_with_completed():
    # 모두 적재되면 100%로 clamp된다(중복 커밋으로 indexed가 total을 넘는 경우 방어).
    response = _make_response(status="INDEXED", total_chunks=10, indexed_chunks=11)

    assert response.progress_percent == 100.0


def test_estimated_seconds_remaining_success_with_no_total_chunks():
    # total_chunks 미확정 상태에서는 잔여 시간을 알 수 없다.
    response = _make_response(status="UPLOADED", total_chunks=None, indexed_chunks=0)

    assert response.estimated_seconds_remaining is None


def test_estimated_seconds_remaining_success_with_no_progress_yet():
    # embedding_started_at은 있지만 아직 청크가 하나도 끝나지 않아 속도를 알 수 없다.
    response = _make_response(
        total_chunks=10,
        indexed_chunks=0,
        embedding_started_at=datetime.now(timezone.utc) - timedelta(seconds=5),
    )

    assert response.estimated_seconds_remaining is None


def test_estimated_seconds_remaining_success_with_linear_estimate():
    # 10초에 5청크 처리 → 속도 0.5청크/s, 남은 5청크 → 약 10초.
    response = _make_response(
        total_chunks=10,
        indexed_chunks=5,
        embedding_started_at=datetime.now(timezone.utc) - timedelta(seconds=10),
    )

    assert response.estimated_seconds_remaining == 10


def test_estimated_seconds_remaining_success_with_indexed_status():
    # 종결 상태(INDEXED)면 진행 중 여부와 무관하게 잔여 시간을 보여주지 않는다.
    response = _make_response(
        status="INDEXED",
        total_chunks=10,
        indexed_chunks=10,
        embedding_started_at=datetime.now(timezone.utc) - timedelta(seconds=10),
    )

    assert response.estimated_seconds_remaining is None


def test_estimated_seconds_remaining_success_with_failed_status():
    # 종결 상태(FAILED)도 동일하게 None.
    response = _make_response(
        status="FAILED",
        total_chunks=10,
        indexed_chunks=3,
        embedding_started_at=datetime.now(timezone.utc) - timedelta(seconds=10),
    )

    assert response.estimated_seconds_remaining is None


def test_document_status_response_success_with_embedding_started_at_excluded():
    # embedding_started_at은 계산용 내부 필드로, 직렬화 결과에는 노출하지 않는다.
    response = _make_response(
        total_chunks=10,
        indexed_chunks=5,
        embedding_started_at=datetime.now(timezone.utc),
    )

    assert "embedding_started_at" not in response.model_dump()
