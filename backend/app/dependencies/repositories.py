from functools import lru_cache

from clients import QdrantDBClient
from dependencies.clients import get_qdrant_client
from repositories import AuthRepository, CollectionMetaRepository
from repositories.vector_db import QdrantRepository


@lru_cache
def get_auth_repository() -> AuthRepository:
    return AuthRepository()


@lru_cache
def get_qdrant_repository() -> QdrantRepository:
    qdrant_client: QdrantDBClient = get_qdrant_client()
    return QdrantRepository(qdrant_client=qdrant_client)


@lru_cache
def get_collection_meta_repository() -> CollectionMetaRepository:
    return CollectionMetaRepository()
