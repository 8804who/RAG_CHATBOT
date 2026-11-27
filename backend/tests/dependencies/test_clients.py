from unittest.mock import patch

from psycopg.conninfo import conninfo_to_dict

from dependencies.clients import checkpointer_conninfo


def test_checkpointer_conninfo_success_with_special_char_password():
    """
    체크포인터 접속 정보 생성(성공) - 비밀번호에 URL 예약 문자 포함

    입력 데이터
        - POSTGRES_PASSWORD = "p@ss/w#rd%40 x"

    예상 출력 데이터
        - 파싱 결과 password가 원문 그대로, host/port/dbname/user 유지
    """
    with patch.multiple(
        "dependencies.clients.config",
        POSTGRES_USER="user",
        POSTGRES_PASSWORD="p@ss/w#rd%40 x",
        POSTGRES_HOST="db",
        POSTGRES_PORT=5432,
        POSTGRES_DB="rag",
    ):
        parsed = conninfo_to_dict(checkpointer_conninfo())

    assert parsed == {
        "user": "user",
        "password": "p@ss/w#rd%40 x",
        "host": "db",
        "port": "5432",
        "dbname": "rag",
    }


def test_checkpointer_conninfo_success_with_plain_password():
    """
    체크포인터 접속 정보 생성(성공) - 일반 비밀번호

    입력 데이터
        - POSTGRES_PASSWORD = "secret"

    예상 출력 데이터
        - password = "secret"
    """
    with patch.multiple(
        "dependencies.clients.config",
        POSTGRES_USER="u",
        POSTGRES_PASSWORD="secret",
        POSTGRES_HOST="h",
        POSTGRES_PORT=1,
        POSTGRES_DB="d",
    ):
        parsed = conninfo_to_dict(checkpointer_conninfo())

    assert parsed["password"] == "secret"
