from fastapi import status

from exceptions.base import AppException


class CollectionMetaNotFoundError(AppException):
    """
    컬렉션은 존재하나 임베딩 모델 정보가 없는 경우
    """

    status_code = status.HTTP_400_BAD_REQUEST
    response_message = "컬렉션의 임베딩 모델 정보를 찾을 수 없습니다"


class EmptyDocumentError(AppException):
    """
    업로드한 문서에서 텍스트를 추출하지 못한 경우
    """

    status_code = status.HTTP_400_BAD_REQUEST
    response_message = "문서 내용이 비어 있습니다"


class DenseVectorNotConfiguredError(AppException):
    """
    컬렉션에 Dense Vector가 없는 경우
    """

    status_code = status.HTTP_400_BAD_REQUEST
    response_message = "컬렉션에 Dense Vector가 구성되어 있지 않습니다"


class DocumentNotFoundError(AppException):
    """
    요청한 document_id의 문서(상태 레코드)가 없는 경우
    """

    status_code = status.HTTP_404_NOT_FOUND
    response_message = "해당 문서가 존재하지 않습니다"
