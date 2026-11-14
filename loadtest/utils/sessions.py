"""
OAuth 우회용 시드 세션 풀 (eval/src/db.ts와 같은 방식, 단일 프로세스 메모리에 보관)
"""

import itertools
import os
import secrets

import psycopg

from core.config import SEED_SESSION_TTL

_tokens: list[str] = []
_assigned = itertools.count()


def _connect_db() -> psycopg.Connection:
    """
    시드용 Postgres 연결 (백엔드·eval과 같은 POSTGRES_* env)

    Returns:
        conn(psycopg.Connection): Postgres 연결
    """
    return psycopg.connect(
        host=os.getenv("POSTGRES_HOST", "localhost"),
        port=int(os.getenv("POSTGRES_PORT", "5432")),
        user=os.getenv("POSTGRES_USER"),
        password=os.getenv("POSTGRES_PASSWORD"),
        dbname=os.getenv("POSTGRES_DB"),
    )


def seed_sessions(count: int) -> int:
    """
    시드 사용자 upsert 후 사용자별 세션 생성 및 풀 교체

    Parameters:
        count(int): 시드 사용자 수

    Returns:
        seeded(int): 생성한 세션 수
    """
    # 왕복 2회로 끝낸다: 협조적(gevent) psycopg가 왕복마다 양보하므로 시드 시간을 줄인다
    with _connect_db() as conn:
        user_ids = [
            row[0]
            for row in conn.execute(
                "INSERT INTO users (google_sub, email, name) "
                "SELECT 'loadtest-' || i, 'loadtest-' || i || '@loadtest.invalid', "
                "'loadtest-' || i FROM generate_series(0, %s - 1) AS i "
                "ON CONFLICT (google_sub) DO UPDATE SET email = EXCLUDED.email "
                "RETURNING id",
                (count,),
            ).fetchall()
        ]
        tokens = [secrets.token_urlsafe(32) for _ in user_ids]
        conn.execute(
            "INSERT INTO google_sessions (token, user_id, expires_at) "
            "SELECT token, user_id, now() + %s::interval "
            "FROM unnest(%s::text[], %s::int[]) AS s(token, user_id)",
            (SEED_SESSION_TTL, tokens, user_ids),
        )
    _tokens[:] = tokens
    return len(tokens)


def has_sessions() -> bool:
    """
    이번 실행의 시드 세션 준비 여부

    Returns:
        ready(bool): 시드가 끝나 세션 풀이 비어 있지 않으면 True
    """
    return bool(_tokens)


def delete_sessions() -> int:
    """
    이번 실행의 시드 세션 삭제 (사용자 행은 다음 실행에서 재사용)

    Returns:
        deleted(int): 삭제한 세션 수
    """
    if not _tokens:
        return 0
    with _connect_db() as conn:
        deleted = conn.execute(
            "DELETE FROM google_sessions WHERE token = ANY(%s)", (_tokens,)
        ).rowcount
    _tokens.clear()
    return deleted


def next_token() -> str:
    """
    Locust 사용자 생성 순번(모든 사용자 클래스 공용) % N으로 시드 세션 선택

    Returns:
        token(str): 쿠키 `session` 값
    """
    return _tokens[next(_assigned) % len(_tokens)]
