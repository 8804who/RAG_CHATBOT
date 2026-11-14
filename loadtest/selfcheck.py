"""
shape 단계표·-t 상한·breakpoint 정지 규칙·시드 게이트·validate_turn 자체 점검 (DB·서버 불필요)

실행 (loadtest/에서): uv run python selfcheck.py
"""

import os
from types import SimpleNamespace

os.environ["LOADTEST_SCENARIO"] = "breakpoint"
os.environ["LOADTEST_TARGET_USERS"] = "50"
os.environ.setdefault("LOADTEST_CHAT_P95_MS", "3000")

import locust.shape
from locust.runners import STATE_INIT, STATE_RUNNING

from core.config import SPAWN_RATE, STAGES
from shapes.scenario import ScenarioShape, target_users
from utils import sessions
from utils.validation import validate_turn

# T=50 단계 경계 (SCENARIOS.md §4 단계표)
EXPECTED = {
    "smoke": {0: 3, 119: 3, 120: None},
    "load": {0: 0, 150: 25, 300: 50, 2099: 50, 2100: None},
    "stress": {300: 50, 900: 50, 1050: 75, 1200: 100, 2999: 100, 3000: None},
    "spike": {0: 0, 30: 8, 60: 15, 315: 83, 330: 150, 905: 83, 910: 15, 1500: None},
    "soak": {300: 50, 14399: 50, 14400: None},
    "breakpoint": {0: 0, 900: 250, 1799: 500, 1800: None},
}
for scenario, points in EXPECTED.items():
    for t, users in points.items():
        got = target_users(STAGES[scenario], t)
        assert got == users, (scenario, t, got, users)

clock = [0.0]
locust.shape.time = SimpleNamespace(perf_counter=lambda: clock[0])


class Entry:
    """채팅 턴 통계 엔트리 가짜 (요청·실패 수와 현재 p95)"""

    num_requests = 0
    num_failures = 0
    p95 = 1000

    def get_current_response_time_percentile(self, _p: float) -> int:
        return self.p95


def make_shape(run_time: int | None = None) -> tuple[ScenarioShape, Entry]:
    """
    가짜 runner를 붙인 breakpoint shape 생성 (시드 완료 상태, 시계 0)

    Parameters:
        run_time(int | None): `-t` 초

    Returns:
        shape(tuple[ScenarioShape, Entry]): shape와 채팅 턴 엔트리
    """
    entry = Entry()
    shape = ScenarioShape()
    shape.runner = SimpleNamespace(
        state=STATE_RUNNING,
        user_count=0,
        stats=SimpleNamespace(get=lambda *_: entry),
        environment=SimpleNamespace(parsed_options=SimpleNamespace(run_time=run_time)),
    )
    sessions._tokens[:] = ["token"]
    clock[0] = 0.0
    shape.reset_time()
    return shape, entry


def run(shape: ScenarioShape, entry: Entry, seconds: int, fail: int = 0) -> int | None:
    """
    1초 간격 tick 반복 (매초 채팅 턴 2건, 그중 fail건 실패)

    Returns:
        stopped_at(int | None): tick이 None을 반환한 시각, 끝까지 안 멈추면 None
    """
    for _ in range(seconds):
        entry.num_requests += 2
        entry.num_failures += fail
        if shape.tick() is None:
            return int(clock[0])
        clock[0] += 1
    return None


# 시드 게이트: 시드 전에는 (0, rate)를 유지하고 램프 시계가 흐르지 않는다
shape, entry = make_shape()
sessions._tokens.clear()
for _ in range(100):
    assert shape.tick() == (0, SPAWN_RATE)
    clock[0] += 1
sessions._tokens[:] = ["token"]
shape.runner.state = STATE_INIT  # 시드 직후, spawn_users 전
assert shape.tick() == (0, SPAWN_RATE)
shape.runner.state = STATE_RUNNING
clock[0] += 1
# 101초가 아니라 시드 완료 후 1초 기준: ceil(500 × 1/1800) = 1
assert shape.tick() == (1, SPAWN_RATE)

# -t 상한 (시드 완료부터 카운트)
shape, entry = make_shape(run_time=90)
assert run(shape, entry, 200) == 90

# 지연 정지: 유예 120초 뒤 p95 위반 30회 연속
shape, entry = make_shape()
assert run(shape, entry, 130) is None
entry.p95 = 5000
assert run(shape, entry, 100) == 159

# 29초 blip은 멈추지 않고, 이후 errors 정지 로그에 이전 onset이 남지 않는다
shape, entry = make_shape()
assert run(shape, entry, 130) is None
entry.p95 = 5000
assert run(shape, entry, 29) is None
entry.p95 = 1000
assert run(shape, entry, 1) is None
assert shape._onset_users is None
assert run(shape, entry, 200) is None

# 오류 정지: 유예 중엔 무시, 유예가 끝나면 60초 창 실패율 > 5%로 정지
shape, entry = make_shape()
assert run(shape, entry, 300, fail=1) == 120


class FakeResponse:
    """catch_response 응답 가짜 (status, json, failure 기록)"""

    def __init__(self, status: int, body: object) -> None:
        self.status_code, self._body, self.failed = status, body, None

    def json(self) -> object:
        if isinstance(self._body, Exception):
            raise self._body
        return self._body

    def failure(self, message: str) -> None:
        self.failed = message


CITED = [{"chunk_id": "c"}]
CASES = [
    (FakeResponse(500, {}), False, "http 500", False),
    (FakeResponse(200, ValueError("bad")), False, "invalid json", False),
    (FakeResponse(200, {"content": "  "}), False, "empty content", False),
    (
        FakeResponse(200, {"content": "real", "citations": CITED}),
        False,
        "non-mock answer",
        True,
    ),
    (
        FakeResponse(200, {"content": "[mock] a", "citations": []}),
        False,
        "empty citations (pinned)",
        False,
    ),
    (FakeResponse(200, {"content": "[mock] a", "citations": []}), True, None, False),
    (
        FakeResponse(200, {"content": "[mock] a", "citations": CITED}),
        False,
        None,
        False,
    ),
]
for response, routed, message, non_mock in CASES:
    assert validate_turn(response, routed) is non_mock, (response._body, routed)
    assert response.failed == message, (response.failed, message)

print("selfcheck OK")
