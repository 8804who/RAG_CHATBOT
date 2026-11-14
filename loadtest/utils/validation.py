"""
채팅 턴 응답 내용 검증 (SCENARIOS.md §5 품질 관문)
"""

from locust.clients import ResponseContextManager


def validate_turn(response: ResponseContextManager, routed: bool) -> bool:
    """
    채팅 턴 응답 검증 후 실패 사유 기록

    Parameters:
        response(ResponseContextManager): catch_response 응답
        routed(bool): routed 모드면 True (인용 검사 생략)

    Returns:
        non_mock(bool): 답변이 `[mock]`으로 시작하지 않으면 True (실제 LLM 과금 신호)
    """
    if response.status_code != 200:
        response.failure(f"http {response.status_code}")
        return False
    try:
        body = response.json()
    except ValueError:
        response.failure("invalid json")
        return False
    content = body.get("content") or ""
    if not content.strip():
        response.failure("empty content")
        return False
    # 과금 방어가 인용 검사보다 우선이다
    if not content.startswith("[mock]"):
        response.failure("non-mock answer")
        return True
    if not routed and not body.get("citations"):
        response.failure("empty citations (pinned)")
    return False
