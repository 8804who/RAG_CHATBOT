from fastapi import APIRouter

from api.v1.endpoints.auth.router import router as auth_router
from api.v1.endpoints.collections import router as collections_router
from api.v1.endpoints.documents import router as documents_router
from api.v1.endpoints.models import router as models_router
from api.v1.endpoints.usage import router as usage_router

router = APIRouter(prefix="/v1")

router.include_router(auth_router)
router.include_router(collections_router)
router.include_router(documents_router)
router.include_router(models_router)
router.include_router(usage_router)
