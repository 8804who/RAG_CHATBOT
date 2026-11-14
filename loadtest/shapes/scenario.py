"""
LOADTEST_SCENARIO 단계표를 따르는 부하 모양 (SCENARIOS.md §4)
"""

import logging
import math
from collections import deque

from locust import LoadTestShape
from locust.runners import STATE_INIT

from core.config import (
    BREAKPOINT_ERROR_MIN_REQUESTS,
    BREAKPOINT_ERROR_RATIO,
    BREAKPOINT_GRACE_S,
    BREAKPOINT_LATENCY_MIN_REQUESTS,
    BREAKPOINT_LATENCY_STREAK,
    CHAT_P95_MS,
    CHAT_TURN_NAME,
    SCENARIO,
    SPAWN_RATE,
    STAGES,
    TARGET_USERS,
)
from utils.sessions import has_sessions

logger = logging.getLogger(__name__)


def target_users(stages: list[tuple[int, int, int]], elapsed: float) -> int | None:
    """
    경과 시간의 목표 사용자 수 계산 (직전 단계 목표에서 램프 동안 선형 보간)

    Parameters:
        stages(list[tuple[int, int, int]]): (길이 초, 목표 사용자 수, 램프 초) 단계 목록
        elapsed(float): 테스트 시작 후 경과 초

    Returns:
        users(int | None): 목표 사용자 수, 모든 단계가 끝났으면 None
    """
    previous, stage_start = 0, 0.0
    for duration, target, ramp in stages:
        if elapsed < stage_start + duration:
            progress = 1.0 if ramp == 0 else min(1.0, (elapsed - stage_start) / ramp)
            return math.ceil(previous + (target - previous) * progress)
        previous, stage_start = target, stage_start + duration
    return None


class ScenarioShape(LoadTestShape):
    """LOADTEST_SCENARIO 단계표를 따르는 부하 모양 (-t와 breakpoint 정지 규칙을 직접 적용)"""

    use_common_options = True

    def __init__(self) -> None:
        super().__init__()
        self.reset_time()

    def reset_time(self) -> None:
        """
        시작 시각과 breakpoint 정지 규칙 상태 초기화
        """
        super().reset_time()
        self._snapshots: deque[tuple[float, int, int]] = deque(maxlen=61)
        self._streak = 0
        self._onset_users: int | None = None

    def tick(self) -> tuple[int, float] | None:
        """
        매 초 목표 사용자 수 계산 (spawn rate는 고정, 램프는 목표값 보간으로 구현)

        Returns:
            tick(tuple[int, float] | None): (목표 사용자 수, spawn rate), 종료 시 None
        """
        # 시드(test_start)가 끝날 때까지 같은 tick을 유지한다. tick이 바뀌면 LocalRunner.start가
        # 시드 중인 spawn 그린렛을 kill하고 test_start가 다시 불린다. 시계는 시드 완료부터 센다
        if not has_sessions() or self.runner.state == STATE_INIT:
            self.reset_time()
            return 0, SPAWN_RATE
        elapsed = self.get_run_time()
        options = self.runner.environment.parsed_options
        run_time = getattr(options, "run_time", None)
        if run_time and elapsed >= run_time:
            return None
        if SCENARIO == "breakpoint" and self._breakpoint_reached(elapsed):
            return None
        users = target_users(STAGES[SCENARIO], elapsed)
        if users is None:
            if SCENARIO == "breakpoint":
                logger.warning(
                    "no breakpoint up to 10×T: T=%d, users_now=%d",
                    TARGET_USERS,
                    self.get_current_user_count(),
                )
            return None
        return users, SPAWN_RATE

    def _breakpoint_reached(self, elapsed: float) -> bool:
        """
        breakpoint 자동 정지 판정 (오류 조건 F: 60초 창 실패율, 지연 조건 L: p95 30초 연속 초과)

        Parameters:
            elapsed(float): 테스트 시작 후 경과 초

        Returns:
            reached(bool): 정지해야 하면 True
        """
        entry = self.runner.stats.get(CHAT_TURN_NAME, "POST")
        self._snapshots.append((elapsed, entry.num_requests, entry.num_failures))
        if elapsed < BREAKPOINT_GRACE_S:
            return False

        _, old_requests, old_failures = self._snapshots[0]
        window_requests = entry.num_requests - old_requests
        window_fail_ratio = (
            (entry.num_failures - old_failures) / window_requests
            if window_requests
            else 0.0
        )
        users_now = self.get_current_user_count()
        chat_p95 = entry.get_current_response_time_percentile(0.95)

        if (
            window_requests >= BREAKPOINT_ERROR_MIN_REQUESTS
            and window_fail_ratio > BREAKPOINT_ERROR_RATIO
        ):
            reason = "errors"
        else:
            # tick이 1초보다 느려 스냅샷이 11개 미만이어도 가장 오래된 것으로 대체
            ten_seconds_ago = self._snapshots[-min(11, len(self._snapshots))]
            recent_requests = entry.num_requests - ten_seconds_ago[1]
            violated = (
                chat_p95 is not None
                and chat_p95 > CHAT_P95_MS
                and recent_requests >= BREAKPOINT_LATENCY_MIN_REQUESTS
            )
            if not violated:
                self._streak = 0
                self._onset_users = None
                return False
            if self._streak == 0:
                self._onset_users = users_now
            self._streak += 1
            if self._streak < BREAKPOINT_LATENCY_STREAK:
                return False
            reason = "latency"

        logger.warning(
            "breakpoint reached: reason=%s, onset_users=%s, users_now=%d, "
            "chat_p95=%s, window_fail_ratio=%.4f",
            reason,
            self._onset_users,
            users_now,
            chat_p95,
            window_fail_ratio,
        )
        return True
