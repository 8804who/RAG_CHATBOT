from functools import lru_cache

from dependencies.repositories import get_auth_repository, get_qdrant_repository
from repositories import AuthRepository
from repositories.vector_db import QdrantRepository
from services.auth import GoogleOAuth2Service
from services.vector_db import QdrantService


@lru_cache
def get_google_oauth2_service() -> GoogleOAuth2Service:
    auth_repository: AuthRepository = get_auth_repository()
    return GoogleOAuth2Service(auth_repository=auth_repository)


@lru_cache
def get_qdrant_service() -> QdrantService:
    qdrant_repository: QdrantRepository = get_qdrant_repository()
    return QdrantService(qdrant_repository=qdrant_repository)
