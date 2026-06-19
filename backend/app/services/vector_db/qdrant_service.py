from repositories.vector_db import QdrantRepository
from schemes.dto.qdrant import CollectionDetail, CollectionSummary
from schemes.requests import (
    CreateQdrantCollectionRequest,
    UpdateQdrantCollectionRequest,
)
from services.vector_db.vector_db_service import VectorDBService


class QdrantService(VectorDBService):
    def __init__(self, qdrant_repository: QdrantRepository):
        self._qdrant_repository = qdrant_repository

    async def get_collections(self) -> list[CollectionSummary]:
        """
        collection 목록 조회

        Returns:
            list[CollectionSummary]: collection 이름 목록
        """
        result = await self._qdrant_repository.get_collections()
        return result

    async def get_collection(self, collection_name: str) -> CollectionDetail:
        """
        collection 단건 상세 조회

        Parameters:
            collection_name(str): 조회할 collection 이름

        Returns:
            CollectionDetail: collection 상세 정보
        """
        result = await self._qdrant_repository.get_collection(collection_name)
        return result

    async def create_collections(
        self, collection_info: CreateQdrantCollectionRequest
    ) -> bool:
        """
        collection 생성

        Parameters:
            collection_info(CreateQdrantCollectionRequest): 생성할 collection 정보

        Returns:
            bool: collection 생성 성공 여부
        """
        result = await self._qdrant_repository.create_collections(collection_info)
        return result

    async def update_collection(
        self, collection_name: str, collection_info: UpdateQdrantCollectionRequest
    ) -> bool:
        """
        collection 수정 가능한 설정 갱신

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

    async def delete_collection(self, collection_name: str) -> bool:
        """
        collection 삭제

        Parameters:
            collection_name(str): 삭제할 collection 이름

        Returns:
            bool: collection 삭제 성공 여부
        """
        result = await self._qdrant_repository.delete_collection(collection_name)
        return result
