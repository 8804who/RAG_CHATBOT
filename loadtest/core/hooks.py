"""
테스트 수명주기 훅: 시드(test_start), 세션 삭제(test_stop), 합격 게이트(quitting)

import하는 것만으로 Locust 이벤트에 등록된다.
"""

import logging

import gevent
from locust import events
from locust.env import Environment

from core.config import (
    CHAT_P95_MS,
    CHAT_TURN_NAME,
    GATED_SCENARIOS,
    MAX_FAIL_RATIO,
    SCENARIO,
    SEED_USERS,
)
from utils.sessions import delete_sessions, seed_sessions

logger = logging.getLogger(__name__)


@events.test_start.add_listener
def on_test_start(environment: Environment, **_kwargs: object) -> None:
    """
    테스트 시작 시 시드 사용자·세션 생성 (첫 사용자 spawn 전에 실행됨)

    Parameters:
        environment(Environment): Locust 환경
    """
    try:
        seeded = seed_sessions(SEED_USERS)
    except Exception:
        logger.exception("시드 실패: 테스트 중단")
        environment.process_exit_code = 1
        # spawn 그린렛 안이라 직접 quit하면 자기 자신을 kill하므로 별도 그린렛에서 종료
        gevent.spawn(environment.runner.quit)
        return
    logger.info("시드 완료: scenario=%s, users=%d", SCENARIO, seeded)


@events.test_stop.add_listener
def on_test_stop(environment: Environment, **_kwargs: object) -> None:
    """
    테스트 종료 시 이번 실행의 시드 세션 삭제

    Parameters:
        environment(Environment): Locust 환경
    """
    try:
        deleted = delete_sessions()
    except Exception:
        logger.exception("시드 세션 삭제 실패 (24시간 뒤 만료됨)")
        environment.process_exit_code = 1
        return
    logger.info("시드 세션 삭제 완료: sessions=%d", deleted)


@events.quitting.add_listener
def on_quitting(environment: Environment, **_kwargs: object) -> None:
    """
    합격 게이트 판정 후 프로세스 종료 코드 설정 (smoke/load/stress/soak만)

    Parameters:
        environment(Environment): Locust 환경
    """
    if SCENARIO not in GATED_SCENARIOS:
        return
    chat = environment.stats.get(CHAT_TURN_NAME, "POST")
    total = environment.stats.total
    chat_p95 = chat.get_response_time_percentile(0.95)
    reasons = []
    if SCENARIO == "smoke":
        if total.num_failures > 0:
            reasons.append(f"failures={total.num_failures} (smoke는 0건이어야 함)")
        if chat.num_requests < 2:
            reasons.append(f"chat_turns={chat.num_requests} (2건 이상 필요)")
    else:
        if chat.num_requests == 0:
            reasons.append("chat_turns=0 (채팅 턴이 1건도 없음)")
        if total.fail_ratio > MAX_FAIL_RATIO:
            reasons.append(f"fail_ratio={total.fail_ratio:.4f} > {MAX_FAIL_RATIO}")
    if environment.runner.exceptions:
        reasons.append(f"locust_exceptions={len(environment.runner.exceptions)}")
    if chat_p95 > CHAT_P95_MS:
        reasons.append(f"chat_p95={chat_p95}ms > {CHAT_P95_MS}ms")

    if reasons:
        logger.error("합격 게이트 실패: %s", "; ".join(reasons))
        environment.process_exit_code = 1
        return
    logger.info(
        "합격 게이트 통과: chat_turns=%d, chat_p95=%dms, fail_ratio=%.4f",
        chat.num_requests,
        chat_p95,
        total.fail_ratio,
    )
    # non-mock 답변으로 이미 1이 설정됐으면 덮어쓰지 않는다
    if environment.process_exit_code is None:
        environment.process_exit_code = 0
