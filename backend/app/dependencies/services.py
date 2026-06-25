from functools import lru_cache

from clients.embedding import (
    BM25SparseEncoder,
    FastEmbedEmbeddingClient,
    OpenAIEmbeddingClient,
    SparseEncoder,
)
from core.config import config
from dependencies.repositories import (
    get_auth_repository,
    get_collection_meta_repository,
    get_qdrant_repository,
)
from repositories import AuthRepository, CollectionMetaRepository
from repositories.vector_db import QdrantRepository
from schemes.dto.embedding import RegisteredEmbeddingModel
from services.auth import GoogleOAuth2Service
from services.embedding import EmbeddingService
from services.ingestion import DocumentService
from services.model_registry import EmbeddingModelRegistry
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
    fastembed_bge_m3 = FastEmbedEmbeddingClient(
        model_name="BAAI/bge-m3", dimension=1024
    )
    openai_small = OpenAIEmbeddingClient(
        model_name="text-embedding-3-small",
        dimension=1536,
        api_key=config.OPENAI_API_KEY,
    )
    openai_large = OpenAIEmbeddingClient(
        model_name="text-embedding-3-large",
        dimension=3072,
        api_key=config.OPENAI_API_KEY,
    )

    catalog = {
        "BAAI/bge-m3": (
            RegisteredEmbeddingModel(
                name="BAAI/bge-m3", provider="fastembed", dimension=1024
            ),
            fastembed_bge_m3,
        ),
        "text-embedding-3-small": (
            RegisteredEmbeddingModel(
                name="text-embedding-3-small", provider="openai", dimension=1536
            ),
            openai_small,
        ),
        "text-embedding-3-large": (
            RegisteredEmbeddingModel(
                name="text-embedding-3-large", provider="openai", dimension=3072
            ),
            openai_large,
        ),
    }
    return EmbeddingModelRegistry(catalog=catalog)


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
        embedding_service=get_embedding_service(),
        collection_meta_repository=get_collection_meta_repository(),
    )


@lru_cache
def get_qdrant_service() -> QdrantService:
    qdrant_repository: QdrantRepository = get_qdrant_repository()
    collection_meta_repository: CollectionMetaRepository = (
        get_collection_meta_repository()
    )
    return QdrantService(
        qdrant_repository=qdrant_repository,
        embedding_registry=get_embedding_registry(),
        collection_meta_repository=collection_meta_repository,
    )
