import secrets
from datetime import UTC, datetime, timedelta

from sqlalchemy.ext.asyncio import AsyncSession
from starlette.requests import Request
from starlette.responses import RedirectResponse

from core.config import config
from core.oauth import oauth
from repositories import AuthRepository
from services.auth.auth_service import AuthSession, AuthService


class GoogleOAuth2Service(AuthService):
    def __init__(self, auth_repository: AuthRepository):
        self._auth_repository = auth_repository

    async def login(self, request: Request) -> RedirectResponse:
        """
        Google OAuth2 로그인 시작.

        Authlib가 state/nonce를 Starlette 세션에 저장한 뒤 사용자를 구글
        인증 화면으로 리다이렉트한다.

        Args:
            request(Request): 들어온 요청 (세션 접근에 필요)

        Returns:
            RedirectResponse: 구글 인증 화면으로의 리다이렉트 응답
        """
        return await oauth.google.authorize_redirect(
            request, config.GOOGLE_REDIRECT_URI
        )

    async def callback(self, request: Request, db: AsyncSession) -> AuthSession:
        """
        구글 콜백 처리: 인가 코드를 토큰으로 교환하고 세션 생성

        Args:
            request(Request): 콜백 요청
            db(AsyncSession): DB 세션

        Returns:
            AuthSession: 생성된 세션 토큰과 사용자 정보
        """
        token = await oauth.google.authorize_access_token(request)
        # OpenID Connect: userinfo is parsed from the verified ID token.
        userinfo = token.get("userinfo")
        if userinfo is None:
            userinfo = await oauth.google.userinfo(token=token)

        user = await self._auth_repository.upsert_user(
            db,
            google_sub=userinfo["sub"],
            email=userinfo["email"],
            name=userinfo.get("name"),
            picture=userinfo.get("picture"),
        )

        session_token = secrets.token_urlsafe(32)
        expires_at = datetime.now(UTC) + timedelta(
            seconds=config.SESSION_TTL_SECONDS
        )
        await self._auth_repository.create_google_session(
            db, user_id=user.id, token=session_token, expires_at=expires_at
        )
        return AuthSession(token=session_token, expires_at=expires_at, user=user)

    async def logout(self, db: AsyncSession, token: str) -> None:
        """
        세션 토큰 폐기

        Args:
            db(AsyncSession): DB 세션
            token(str): 세션 토큰
        """
        await self._auth_repository.delete_google_session(db, token)
