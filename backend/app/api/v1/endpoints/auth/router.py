from fastapi import APIRouter

from api.v1.endpoints.auth.google_auth import router as google_auth_router
from api.v1.endpoints.auth.auth import router as auth_router

router = APIRouter(prefix="/auth")

router.include_router(google_auth_router)
router.include_router(auth_router)
