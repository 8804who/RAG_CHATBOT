from fastapi import status

from exceptions.base import AppException


class UnsupportedEmbeddingModelError(AppException):
    """
    등록되지 않은 임베딩 모델을 요청한 경우
    """

    status_code = status.HTTP_400_BAD_REQUEST
    response_message = "지원하지 않는 임베딩 모델입니다"


class EmbeddingModelDimensionMismatchError(AppException):
    """
    요청 dimension이 등록된 모델 차원과 다른 경우
    """

    status_code = status.HTTP_400_BAD_REQUEST
    response_message = "임베딩 모델 차원이 일치하지 않습니다"


class EmbeddingGenerationError(AppException):
    """
    임베딩 과정에서 오류가 발생한 경우
    """

    status_code = status.HTTP_502_BAD_GATEWAY
    response_message = "임베딩 생성에 실패했습니다"
