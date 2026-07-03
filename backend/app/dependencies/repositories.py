from functools import lru_cache

from clients import QdrantDBClient
from dependencies.clients import get_qdrant_client
from repositories import (
    AuthRepository,
    CollectionMetadataRepository,
    DocumentStatusRepository,
    LogRepository,
)
from repositories.vector_db import QdrantRepository


@lru_cache
def get_auth_repository() -> AuthRepository:
    return AuthRepository()


@lru_cache
def get_qdrant_repository() -> QdrantRepository:
    qdrant_client: QdrantDBClient = get_qdrant_client()
    return QdrantRepository(qdrant_client=qdrant_client)


@lru_cache
def get_collection_meta_repository() -> CollectionMetadataRepository:
    return CollectionMetadataRepository()


@lru_cache
def get_log_repository() -> LogRepository:
    return LogRepository()


@lru_cache
def get_document_status_repository() -> DocumentStatusRepository:
    return DocumentStatusRepository()
