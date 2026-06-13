from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime

from sqlalchemy.ext.asyncio import AsyncSession
from starlette.requests import Request
from starlette.responses import RedirectResponse

from models import User


@dataclass
class AuthSession:
    """Result of a completed login: the opaque session token plus the user."""

    token: str
    expires_at: datetime
    user: User


class AuthService(ABC):
    @abstractmethod
    async def login(self, request: Request) -> RedirectResponse:
        """Start the OAuth flow by redirecting the user to the provider."""

    @abstractmethod
    async def logout(self, db: AsyncSession, token: str) -> None:
        """Revoke the given session token."""
