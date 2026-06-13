from datetime import datetime

from pydantic import BaseModel, ConfigDict


class LoginResponse(BaseModel):
    # Opaque session token; the client sends it as `Authorization: Bearer <token>`.
    access_token: str
    token_type: str = "bearer"
    expires_at: datetime


class UserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    email: str
    name: str | None
    picture: str | None
