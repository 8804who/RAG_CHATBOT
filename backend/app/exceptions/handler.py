import logging

from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse

from exceptions.base import BaseAppException

logger = logging.getLogger(__name__)


async def app_exception_handler(
    request: Request, exc: BaseAppException
) -> JSONResponse:
    """
    커스텀 예외 처리

    Parameters:
        request: 예외가 발생한 요청
        exc: 서비스/레포지토리에서 발생시킨 커스텀 예외

    Returns:
        예외의 status_code와 message를 담은 JSON 응답
    """
    # 내부 추적용으로만 code_path를 남기고, 프론트엔드에는 message만 노출한다.
    logger.error("%s\n오류 발생 위치: %s", exc.message, exc.code_path)
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": exc.message},
    )


async def unhandled_exception_handler(
    request: Request, exc: Exception
) -> JSONResponse:
    """
    예상하지 못한 예외 처리

    Parameters:
        request: 예외가 발생한 요청
        exc: 커스텀 예외가 아닌 모든 예외

    Returns:
        내부 정보를 감춘 500 JSON 응답.
    """
    # 전체 스택 트레이스는 로그로만 남기고, 프론트엔드에는 일반 메시지를 반환한다.
    logger.exception("%s\n오류 발생 위치: %s", request.method, request.url.path)
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"detail": "일시적으로 장애가 발생하였습니다."},
    )


def register_exception_handlers(app: FastAPI) -> None:
    """앱에 예외 핸들러 등록.

    Parameters:
        app: 핸들러를 등록할 FastAPI 인스턴스.

    Returns:
        없음.
    """
    app.add_exception_handler(BaseAppException, app_exception_handler)
    app.add_exception_handler(Exception, unhandled_exception_handler)
