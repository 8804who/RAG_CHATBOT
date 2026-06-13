from datetime import datetime

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from models import GoogleSession, User


class AuthRepository:
    def __init__(self) -> None:
        pass

    async def get_user_by_id(self, db: AsyncSession, user_id: int) -> User | None:
        return await db.get(User, user_id)

    async def get_user_by_google_sub(
        self, db: AsyncSession, google_sub: str
    ) -> User | None:
        result = await db.execute(
            select(User).where(User.google_sub == google_sub)
        )
        return result.scalar_one_or_none()

    async def upsert_user(
        self,
        db: AsyncSession,
        google_sub: str,
        email: str,
        name: str | None,
        picture: str | None,
    ) -> User:
        user = await self.get_user_by_google_sub(db, google_sub)
        if user is None:
            user = User(google_sub=google_sub)
            db.add(user)
        user.email = email
        user.name = name
        user.picture = picture
        await db.commit()
        await db.refresh(user)
        return user

    async def create_google_session(
        self,
        db: AsyncSession,
        user_id: int,
        token: str,
        expires_at: datetime,
    ) -> GoogleSession:
        session = GoogleSession(token=token, user_id=user_id, expires_at=expires_at)
        db.add(session)
        await db.commit()
        return session

    async def get_google_session(
        self, db: AsyncSession, token: str, now: datetime
    ) -> GoogleSession | None:
        result = await db.execute(
            select(GoogleSession).where(
                GoogleSession.token == token,
                GoogleSession.expires_at > now,
            )
        )
        return result.scalar_one_or_none()

    async def delete_google_session(self, db: AsyncSession, token: str) -> None:
        await db.execute(
            delete(GoogleSession).where(GoogleSession.token == token)
        )
        await db.commit()
