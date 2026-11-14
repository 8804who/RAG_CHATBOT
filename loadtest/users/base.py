"""
시드 세션 쿠키로 인증하는 사용자 공통 부모
"""

from locust import HttpUser

from utils.sessions import next_token


class SeededUser(HttpUser):
    """시드 세션 쿠키로 인증하는 사용자 공통 부모"""

    abstract = True

    def on_start(self) -> None:
        """
        시드 세션 1개를 골라 쿠키 `session`에 설정
        """
        self.client.cookies.set("session", next_token())
