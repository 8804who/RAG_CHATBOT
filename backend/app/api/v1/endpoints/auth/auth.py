from typing import Annotated

from fastapi import APIRouter, Depends

from dependencies.auth import get_current_user
from models import User
from schemes.responses import UserResponse

router = APIRouter(tags=["Auth"])


@router.get("/me", response_model=UserResponse)
async def me(user: Annotated[User, Depends(get_current_user)]) -> User:
    """Return the currently authenticated user, or 401 if not logged in."""
    return user
