from fastapi import status

from exceptions.base import AppException


class CollectionNotFoundError(AppException):
    """
    존재하지 않는 collection에 접근/수정/삭제를 시도한 경우
    """

    status_code = status.HTTP_404_NOT_FOUND
    response_message = "해당 collection이 존재하지 않습니다"


class CollectionAlreadyExistsError(AppException):
    """
    이미 존재하는 이름으로 collection 생성을 시도한 경우
    """

    status_code = status.HTTP_409_CONFLICT
    response_message = "이미 존재하는 collection 명 입니다"
