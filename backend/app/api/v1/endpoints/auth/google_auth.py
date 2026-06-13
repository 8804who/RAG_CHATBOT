from fastapi import APIRouter, Depends, Request, Response, status
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.responses import RedirectResponse

from core.config import config
from dependencies.db import get_db_session
from dependencies.services import get_google_oauth2_service
from services.auth import GoogleOAuth2Service

router = APIRouter(prefix="/google", tags=["GoogleOAuth2"])


@router.get("/login")
async def google_oauth_login(
    request: Request,
    google_oauth2_service: GoogleOAuth2Service = Depends(get_google_oauth2_service),
) -> RedirectResponse:
    """Redirect the user to Google's consent screen."""
    return await google_oauth2_service.login(request)


@router.get("/callback")
async def google_oauth_callback(
    request: Request,
    db: AsyncSession = Depends(get_db_session),
    google_oauth2_service: GoogleOAuth2Service = Depends(get_google_oauth2_service),
) -> RedirectResponse:
    """Complete the OAuth flow, set the session cookie, and return to the app."""
    auth_session = await google_oauth2_service.callback(request, db)
    response = RedirectResponse(config.FRONTEND_URL)
    response.set_cookie(
        key=config.SESSION_COOKIE_NAME,
        value=auth_session.token,
        httponly=True,
        secure=config.SESSION_COOKIE_SECURE,
        samesite="lax",
        max_age=config.SESSION_TTL_SECONDS,
    )
    return response


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def google_oauth_logout(
    request: Request,
    response: Response,
    db: AsyncSession = Depends(get_db_session),
    google_oauth2_service: GoogleOAuth2Service = Depends(get_google_oauth2_service),
) -> None:
    """Revoke the current session and clear the cookie."""
    token = request.cookies.get(config.SESSION_COOKIE_NAME)
    if token:
        await google_oauth2_service.logout(db, token)
    response.delete_cookie(config.SESSION_COOKIE_NAME)
