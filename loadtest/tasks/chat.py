"""
ChatUser task: 페이지 진입 → 채팅 생성 → 1~5턴 (SCENARIOS.md §2)
"""

import logging
import random

import gevent
from locust import HttpUser

from core.config import (
    CHAT_MODEL,
    CHAT_TURN_NAME,
    COLLECTION,
    PAGE_LOAD_PATHS,
    QUERIES,
    REQUEST_TIMEOUT_S,
)
from utils.http import get_ok
from utils.validation import validate_turn

logger = logging.getLogger(__name__)


def chat_session(user: HttpUser) -> None:
    """
    채팅 세션 1회 (페이지 로드 → 채팅 생성 → 턴마다 생각 시간 후 메시지 전송)

    Parameters:
        user(HttpUser): `routed` 속성을 가진 ChatUser
    """
    for path in PAGE_LOAD_PATHS:
        get_ok(user, path)
    chat_id = _create_chat(user)
    if chat_id is None:
        return
    for _ in range(random.randint(1, 5)):
        user.wait()
        _send_turn(user, chat_id)


def _create_chat(user: HttpUser) -> str | None:
    """
    채팅 생성 (pinned면 컬렉션 고정, routed면 collection_name 생략)

    Parameters:
        user(HttpUser): ChatUser

    Returns:
        chat_id(str | None): 생성된 채팅 ID, 실패 시 None
    """
    body = {"chat_model": CHAT_MODEL}
    if not user.routed:
        body["collection_name"] = COLLECTION
    with user.client.post(
        "/api/v1/chats", json=body, catch_response=True, timeout=REQUEST_TIMEOUT_S
    ) as response:
        if response.status_code != 201:
            response.failure(f"http {response.status_code}")
            return None
        try:
            chat_id = response.json().get("id")
        except ValueError:
            response.failure("invalid json")
            return None
        if not chat_id:
            response.failure("empty chat id")
        return chat_id or None


def _send_turn(user: HttpUser, chat_id: str) -> None:
    """
    채팅 턴 1회 전송 후 내용 검증 (실제 OpenAI 답변이면 즉시 테스트 중단)

    Parameters:
        user(HttpUser): ChatUser
        chat_id(str): 채팅 ID
    """
    with user.client.post(
        f"/api/v1/chats/{chat_id}/messages",
        json={"query": random.choice(QUERIES)},
        name=CHAT_TURN_NAME,
        catch_response=True,
        timeout=REQUEST_TIMEOUT_S,
    ) as response:
        non_mock = validate_turn(response, user.routed)
    if non_mock:
        logger.error("실제 LLM 답변 감지: 과금 방지를 위해 테스트 중단")
        user.environment.process_exit_code = 1
        # 현재 사용자 그린렛 안에서 quit하면 자신이 kill되며 test_stop(세션 삭제)이 끊길 수 있다
        gevent.spawn(user.environment.runner.quit)
