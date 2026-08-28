from fastapi import status

from exceptions.base import AppException


class ChatNotFoundError(AppException):
    """
    요청한 chat_id의 채팅이 없는 경우
    """

    status_code = status.HTTP_404_NOT_FOUND
    response_message = "해당 채팅이 존재하지 않습니다"


class ChatAccessDeniedError(AppException):
    """
    다른 사용자의 채팅에 접근하려는 경우(IDOR 방지)
    """

    status_code = status.HTTP_403_FORBIDDEN
    response_message = "해당 채팅에 접근할 권한이 없습니다"


class UnsupportedChatModelError(AppException):
    """
    등록되지 않은 채팅 모델을 요청한 경우
    """

    status_code = status.HTTP_400_BAD_REQUEST
    response_message = "지원하지 않는 채팅 모델입니다"
