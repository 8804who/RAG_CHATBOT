from functools import lru_cache

from clients.embedding import (
    BM25SparseEncoder,
    SparseEncoder,
)
from core.model_config.embedding_model_config import embedding_model_catalog
from dependencies.clients import get_kafka_producer
from dependencies.repositories import (
    get_auth_repository,
    get_collection_meta_repository,
    get_document_status_repository,
    get_log_repository,
    get_pricing_repository,
    get_qdrant_repository,
)
from repositories import AuthRepository, CollectionMetadataRepository
from repositories.vector_db import QdrantRepository
from services.auth import GoogleOAuth2Service
from services.embedding import EmbeddingService
from services.ingestion import (
    DocumentService,
    EmbedIngestService,
    IndexService,
    ParserService,
)
from services.model_registry import EmbeddingModelRegistry
from services.usage import UsageStatsService
from services.vector_db import QdrantService


@lru_cache
def get_google_oauth2_service() -> GoogleOAuth2Service:
    auth_repository: AuthRepository = get_auth_repository()
    return GoogleOAuth2Service(auth_repository=auth_repository)


@lru_cache
def get_embedding_registry() -> EmbeddingModelRegistry:
    """
    임베딩 모델 목록
    """
    return EmbeddingModelRegistry(catalog=embedding_model_catalog)


@lru_cache
def get_sparse_encoder() -> SparseEncoder:
    return BM25SparseEncoder()


@lru_cache
def get_embedding_service() -> EmbeddingService:
    return EmbeddingService(
        embedding_registry=get_embedding_registry(),
        sparse_encoder=get_sparse_encoder(),
    )


@lru_cache
def get_document_service() -> DocumentService:
    return DocumentService(
        qdrant_repository=get_qdrant_repository(),
        kafka_producer=get_kafka_producer(),
        document_status_repository=get_document_status_repository(),
        log_repository=get_log_repository(),
    )


@lru_cache
def get_parser_service() -> ParserService:
    return ParserService(
        qdrant_repository=get_qdrant_repository(),
        collection_meta_repository=get_collection_meta_repository(),
        document_status_repository=get_document_status_repository(),
        kafka_producer=get_kafka_producer(),
    )


@lru_cache
def get_embed_ingest_service() -> EmbedIngestService:
    return EmbedIngestService(
        embedding_service=get_embedding_service(),
        document_status_repository=get_document_status_repository(),
        kafka_producer=get_kafka_producer(),
    )


@lru_cache
def get_index_service() -> IndexService:
    return IndexService(
        qdrant_repository=get_qdrant_repository(),
        document_status_repository=get_document_status_repository(),
        log_repository=get_log_repository(),
    )


@lru_cache
def get_usage_stats_service() -> UsageStatsService:
    return UsageStatsService(
        log_repository=get_log_repository(),
        pricing_repository=get_pricing_repository(),
    )


@lru_cache
def get_qdrant_service() -> QdrantService:
    qdrant_repository: QdrantRepository = get_qdrant_repository()
    collection_meta_repository: CollectionMetadataRepository = (
        get_collection_meta_repository()
    )
    return QdrantService(
        qdrant_repository=qdrant_repository,
        embedding_registry=get_embedding_registry(),
        collection_meta_repository=collection_meta_repository,
    )
