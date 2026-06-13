from datetime import UTC, datetime
from typing import Annotated

from fastapi import Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from core.config import config
from dependencies.db import get_db_session
from dependencies.repositories import get_auth_repository
from models import User
from repositories import AuthRepository


async def get_current_user(
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db_session)],
    auth_repository: Annotated[AuthRepository, Depends(get_auth_repository)],
) -> User:
    token = request.cookies.get(config.SESSION_COOKIE_NAME)
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated"
        )

    session = await auth_repository.get_google_session(db, token, datetime.now(UTC))
    if session is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired session",
        )

    user = await auth_repository.get_user_by_id(db, session.user_id)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found"
        )
    return user
