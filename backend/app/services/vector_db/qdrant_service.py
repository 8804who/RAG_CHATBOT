from repositories.vector_db import QdrantRepository
from schemes.requests import CreateQdrantCollectionRequest
from services.vector_db.vector_db_service import VectorDBService


class QdrantService(VectorDBService):
    def __init__(self, qdrant_repository: QdrantRepository):
        self._qdrant_repository = qdrant_repository

    async def get_collections(self):
        """
        collection 목록 조회
        """
        result = await self._qdrant_repository.get_collections()
        return result

    async def create_collections(self, collection_info: CreateQdrantCollectionRequest) -> bool:
        """
        collection 생성

        Parameters:
            request(CreateQdrantCollectionRequest): 생성할 collection 정보

        Returns:
            bool: collection 생성 성공 여부
        """
        result = await self._qdrant_repository.create_collections(collection_info)
        return result
