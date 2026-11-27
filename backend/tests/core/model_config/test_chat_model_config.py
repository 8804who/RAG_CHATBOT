import pytest

from core.constants import (
    CHAT_MODEL_MAX_RETRIES,
    CHAT_MODEL_TIMEOUT_SECONDS,
    CHAT_SUMMARY_MODEL,
    DEFAULT_CHAT_MAX_COMPLETION_TOKENS,
)
from core.model_config.chat_model_config import chat_model_catalog


@pytest.mark.parametrize("name", sorted(chat_model_catalog))
def test_chat_model_catalog_success_with_server_limits(name):
    """
    채팅 모델 카탈로그(성공) - 모든 모델에 서버 강제 상한 적용

    입력 데이터
        - 등록된 각 채팅 모델

    예상 출력 데이터
        - max_tokens = 1024, timeout = 60초, max_retries = 2
    """
    _, model = chat_model_catalog[name]

    assert model.max_tokens == DEFAULT_CHAT_MAX_COMPLETION_TOKENS
    assert model.request_timeout == CHAT_MODEL_TIMEOUT_SECONDS
    assert model.max_retries == CHAT_MODEL_MAX_RETRIES


def test_chat_model_catalog_success_with_summary_model_registered():
    """
    채팅 모델 카탈로그(성공) - 요약 모델이 등록 모델 중 하나

    입력 데이터
        - CHAT_SUMMARY_MODEL

    예상 출력 데이터
        - 카탈로그에 존재(미등록이면 매 턴 resolve 실패)
    """
    assert CHAT_SUMMARY_MODEL in chat_model_catalog
