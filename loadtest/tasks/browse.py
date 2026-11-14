"""
BrowseUser task: 컬렉션 → 문서 → 사용량 (SCENARIOS.md §2)
"""

from locust import HttpUser

from core.config import COLLECTION
from utils.http import get_ok


def browse(user: HttpUser) -> None:
    """
    컬렉션 목록 → 문서 목록 → 사용량 통계 조회 (사이마다 대기)

    Parameters:
        user(HttpUser): BrowseUser
    """
    get_ok(user, "/api/v1/collections")
    user.wait()
    get_ok(
        user,
        f"/api/v1/collections/{COLLECTION}/documents",
        name="/api/v1/collections/[name]/documents",
    )
    user.wait()
    get_ok(user, "/api/v1/usage/stats")
