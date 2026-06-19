from fastapi import APIRouter

from api.v1.endpoints.auth.router import router as auth_router
from api.v1.endpoints.collections import router as collections_router

router = APIRouter(prefix="/v1")

router.include_router(auth_router)
router.include_router(collections_router)
