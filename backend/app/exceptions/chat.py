from fastapi import status

from exceptions.base import AppException


class ChatNotFoundError(AppException):
    """
    요청한 chat_id의 채팅이 없는 경우
    """

    status_code = status.HTTP_404_NOT_FOUND
    response_message = "Chat not found."


class ChatAccessDeniedError(AppException):
    """
    다른 사용자의 채팅에 접근하려는 경우(IDOR 방지)
    """

    status_code = status.HTTP_403_FORBIDDEN
    response_message = "You do not have access to this chat."


class UnsupportedChatModelError(AppException):
    """
    등록되지 않은 채팅 모델을 요청한 경우
    """

    status_code = status.HTTP_400_BAD_REQUEST
    response_message = "지원하지 않는 채팅 모델입니다"


class ChatTurnInProgressError(AppException):
    """
    같은 채팅에서 이전 메시지 처리가 아직 진행 중인 경우(채팅당 동시 턴 1개)
    """

    status_code = status.HTTP_409_CONFLICT
    response_message = "A previous message in this chat is still being processed. Please retry shortly."
