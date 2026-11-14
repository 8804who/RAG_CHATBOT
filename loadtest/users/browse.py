"""
BrowseUser: 목록 화면 사용자 (weight 1)
"""

from typing import ClassVar

from locust import between

from tasks.browse import browse
from users.base import SeededUser


class BrowseUser(SeededUser):
    """목록 화면 사용자: 컬렉션 → 문서 → 사용량"""

    weight = 1
    wait_time = between(2, 5)
    tasks: ClassVar[list] = [browse]
