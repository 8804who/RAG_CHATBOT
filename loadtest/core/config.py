"""
부하 테스트 설정: env 검증, 상수, 질의 코퍼스, 시나리오 단계표 (SCENARIOS.md §2~§4)

import 시점에 `LOADTEST_SCENARIO`/`LOADTEST_TARGET_USERS`를 검증하고, 잘못되면 유효값을 출력하고 종료한다.
"""

import json
import math
import os
import sys
from pathlib import Path

SCENARIOS = ("smoke", "load", "stress", "spike", "soak", "breakpoint")
GATED_SCENARIOS = ("smoke", "load", "stress", "soak")
CHAT_TURN_NAME = "/api/v1/chats/[chat_id]/messages"
PAGE_LOAD_PATHS = ("/api/v1/auth/me", "/api/v1/models", "/api/v1/collections")
REQUEST_TIMEOUT_S = 60
SPAWN_RATE = 100
SEED_SESSION_TTL = "24 hours"
MAX_FAIL_RATIO = 0.01
# breakpoint 정지 규칙 (SCENARIOS.md §4.6)
BREAKPOINT_GRACE_S = 120
BREAKPOINT_ERROR_MIN_REQUESTS = 20
BREAKPOINT_ERROR_RATIO = 0.05
BREAKPOINT_LATENCY_MIN_REQUESTS = 10
BREAKPOINT_LATENCY_STREAK = 30

SCENARIO = os.getenv("LOADTEST_SCENARIO", "smoke")
if SCENARIO not in SCENARIOS:
    sys.exit(
        f"LOADTEST_SCENARIO={SCENARIO!r}는 유효하지 않음. 유효값: {', '.join(SCENARIOS)}"
    )

_target_users_env = os.getenv("LOADTEST_TARGET_USERS", "50")
TARGET_USERS = int(_target_users_env) if _target_users_env.isdigit() else 0
if TARGET_USERS < 1:
    sys.exit(
        f"LOADTEST_TARGET_USERS={_target_users_env!r}는 유효하지 않음. 유효값: 1 이상의 정수"
    )

_DATASET = json.loads(
    (
        Path(__file__).resolve().parents[2]
        / "eval"
        / "fixtures"
        / "golden-dataset.json"
    ).read_text()
)
QUERIES = [item["query"] for item in _DATASET]
CHAT_MODEL = _DATASET[0]["chatModel"]
COLLECTION = os.getenv("LOADTEST_COLLECTION", _DATASET[0]["collectionName"])
CHAT_P95_MS = int(os.getenv("LOADTEST_CHAT_P95_MS", "3000"))


def u(multiplier: float) -> int:
    """
    T 배수를 사용자 수로 변환

    Parameters:
        multiplier(float): 목표 배수 (예: 1.0, 0.3)

    Returns:
        users(int): max(1, ceil(multiplier × T))
    """
    return max(1, math.ceil(multiplier * TARGET_USERS))


# 단계 = (길이 초, 목표 사용자 수, 램프 초). SCENARIOS.md §4 단계표와 1:1
STAGES: dict[str, list[tuple[int, int, int]]] = {
    "smoke": [(120, 3, 0)],
    "load": [(300, u(1.0), 300), (1800, u(1.0), 0)],
    "stress": [
        (300, u(1.0), 300),
        (600, u(1.0), 0),
        (300, u(2.0), 300),
        (1800, u(2.0), 0),
    ],
    "spike": [(300, u(0.3), 60), (600, u(3.0), 30), (600, u(0.3), 10)],
    "soak": [(300, u(1.0), 300), (14100, u(1.0), 0)],
    "breakpoint": [(1800, u(10.0), 1800)],
}
SEED_USERS = max(target for _, target, _ in STAGES[SCENARIO])
