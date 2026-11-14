"""
공통 HTTP 요청 헬퍼
"""

from locust import HttpUser

from core.config import REQUEST_TIMEOUT_S


def get_ok(user: HttpUser, path: str, name: str | None = None) -> None:
    """
    GET 요청 후 200 여부 검증

    Parameters:
        user(HttpUser): 요청을 보낼 Locust 사용자
        path(str): 요청 경로
        name(str | None): Locust 통계 이름 (None이면 경로 그대로)
    """
    with user.client.get(
        path, name=name, catch_response=True, timeout=REQUEST_TIMEOUT_S
    ) as response:
        if response.status_code != 200:
            response.failure(f"http {response.status_code}")
