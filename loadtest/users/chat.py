"""
ChatUser: 채팅 세션 사용자 (weight 4)
"""

import itertools
from typing import ClassVar

from locust import between

from tasks.chat import chat_session
from users.base import SeededUser


class ChatUser(SeededUser):
    """채팅 세션 사용자 (pinned/routed는 생성 순번으로 고정)"""

    weight = 4
    wait_time = between(3, 10)
    tasks: ClassVar[list] = [chat_session]
    _created = itertools.count()

    def on_start(self) -> None:
        """
        세션 쿠키 설정 후 pinned/routed 모드 고정 (클래스 생성 순번 n % 3 == 1이면 routed)
        """
        super().on_start()
        self.routed = next(ChatUser._created) % 3 == 1
