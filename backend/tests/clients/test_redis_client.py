from unittest.mock import patch

from clients.redis_client import RedisClient


def _build(password: str) -> dict:
    with (
        patch.multiple(
            "clients.redis_client.config",
            REDIS_HOST="redis",
            REDIS_PORT=6379,
            REDIS_DB=0,
            REDIS_PASSWORD=password,
        ),
        patch("clients.redis_client.redis.Redis") as redis_cls,
    ):
        RedisClient()
    return redis_cls.call_args.kwargs


def test_init_success_with_password_passed():
    """
    Redis 클라이언트 생성(성공) - 비밀번호 설정된 Redis(KI-057)

    입력 데이터
        - REDIS_PASSWORD = "secret"

    예상 출력 데이터
        - redis.Redis(password="secret", host/port/db 유지)
    """
    kwargs = _build("secret")

    assert kwargs["password"] == "secret"
    assert (kwargs["host"], kwargs["port"], kwargs["db"]) == ("redis", 6379, 0)


def test_init_success_with_empty_password_as_none():
    """
    Redis 클라이언트 생성(성공) - 비밀번호 없는 로컬 Redis

    입력 데이터
        - REDIS_PASSWORD = ""

    예상 출력 데이터
        - password=None(AUTH 미전송)
    """
    assert _build("")["password"] is None
