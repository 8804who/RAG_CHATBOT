from fastapi.testclient import TestClient

from main import app


def test_metrics_success_with_prior_request():
    """
    Prometheus 메트릭 노출(성공)

    입력 데이터
        - GET /health 1회 호출 후 GET /metrics

    예상 출력 데이터
        - 200 응답, http_request 계열 메트릭과 /health 라우트 템플릿 라벨 포함
        - /metrics 자체는 계측 대상에서 제외
    """
    # lifespan(Postgres/Kafka 연결)을 띄우지 않도록 컨텍스트 매니저 없이 사용한다.
    client = TestClient(app)
    client.get("/health")

    response = client.get("/metrics")

    assert response.status_code == 200
    assert "http_requests_total" in response.text
    assert "http_request_duration_seconds" in response.text
    assert 'handler="/health"' in response.text
    assert 'handler="/metrics"' not in response.text
