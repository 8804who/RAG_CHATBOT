from sqlalchemy.ext.asyncio import AsyncSession

from exceptions.embedding import EmbeddingModelDimensionMismatchError
from repositories import CollectionMetaRepository
from repositories.vector_db import QdrantRepository
from schemes.dto.qdrant import CollectionDetail, CollectionSummary
from schemes.requests import (
    CreateQdrantCollectionRequest,
    UpdateQdrantCollectionRequest,
)
from services.model_registry import EmbeddingModelRegistry
from services.vector_db.vector_db_service import VectorDBService


class QdrantService(VectorDBService):
    def __init__(
        self,
        qdrant_repository: QdrantRepository,
        embedding_registry: EmbeddingModelRegistry,
        collection_meta_repository: CollectionMetaRepository,
    ):
        self._qdrant_repository = qdrant_repository
        self._embedding_registry = embedding_registry
        self._collection_meta_repository = collection_meta_repository

    async def get_collections(self) -> list[CollectionSummary]:
        """
        collection 목록 조회

        Returns:
            list[CollectionSummary]: collection 이름 목록
        """
        result = await self._qdrant_repository.get_collections()
        return result

    async def get_collection(
        self, db: AsyncSession, collection_name: str
    ) -> CollectionDetail:
        """
        collection 상세 조회

        Parameters:
            db(AsyncSession): DB 세션
            collection_name(str): 조회할 collection 이름

        Returns:
            CollectionDetail: collection 상세 정보
        """
        result = await self._qdrant_repository.get_collection(collection_name)
        meta = await self._collection_meta_repository.get(db, collection_name)
        if meta is not None:
            result.embedding_model = meta.embedding_model
        return result

    async def create_collections(
        self, db: AsyncSession, collection_info: CreateQdrantCollectionRequest
    ) -> bool:
        """
        collection 생성

        Parameters:
            db(AsyncSession): DB 세션
            collection_info(CreateQdrantCollectionRequest): 생성할 collection 정보

        Returns:
            bool: collection 생성 성공 여부
        """
        model = collection_info.embedding_model
        # 미등록 모델이면 UnsupportedEmbeddingModelError(400)
        registered = self._embedding_registry.get_info(model.name)
        if registered.dimension != model.dimension:
            raise EmbeddingModelDimensionMismatchError(
                message=(
                    f"embedding model '{model.name}' dimension "
                    f"({registered.dimension}) != requested ({model.dimension})"
                ),
                code_path="qdrant_service-create_collections-error",
            )

        result = await self._qdrant_repository.create_collections(collection_info)
        await self._collection_meta_repository.create(
            db,
            collection_name=collection_info.collection_name,
            embedding_model=model.name,
            dimension=model.dimension,
        )
        return result

    async def update_collection(
        self, collection_name: str, collection_info: UpdateQdrantCollectionRequest
    ) -> bool:
        """
        collection 설정 갱신

        Parameters:
            collection_name(str): 수정할 collection 이름
            collection_info(UpdateQdrantCollectionRequest): 갱신할 설정

        Returns:
            bool: collection 갱신 성공 여부
        """
        result = await self._qdrant_repository.update_collection(
            collection_name, collection_info
        )
        return result

    async def delete_collection(self, db: AsyncSession, collection_name: str) -> bool:
        """
        collection 삭제

        Parameters:
            db(AsyncSession): DB 세션(컬렉션 메타 삭제용)
            collection_name(str): 삭제할 collection 이름
        """
        await self._qdrant_repository.delete_collection(collection_name)
        await self._collection_meta_repository.delete(db, collection_name)
