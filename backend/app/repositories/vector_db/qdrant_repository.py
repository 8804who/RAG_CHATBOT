from qdrant_client import models

from clients import QdrantDBClient
from repositories.vector_db.vector_db_repository import VectorDBRepository
from schemes.requests import CreateQdrantCollectionRequest


class QdrantRepository(VectorDBRepository):
    def __init__(self, qdrant_client: QdrantDBClient):
        self._qdrant_client = qdrant_client

    async def get_collections(self):
        result = await self._qdrant_client.client.get_collections()
        return result

    async def create_collections(self, request: CreateQdrantCollectionRequest) -> bool:
        """
        Qdrant collection 생성

        Parameters:
            request(CreateQdrantCollectionRequest): 생성할 collection 정보

        Returns:
            bool: collection 생성 성공 여부
        """
        vectors_config = {
            name: models.VectorParams(
                size=cfg.size,
                distance=models.Distance(cfg.distance.value),
                on_disk=cfg.on_disk,
            )
            for name, cfg in request.dense_vectors.items()
        }
        sparse_vectors_config = {
            name: models.SparseVectorParams(
                modifier=models.Modifier(cfg.modifier.value),
                index=models.SparseIndexParams(on_disk=cfg.on_disk),
            )
            for name, cfg in request.sparse_vectors.items()
        }
        result = await self._qdrant_client.client.create_collection(
            collection_name=request.collection_name,
            vectors_config=vectors_config,
            sparse_vectors_config=sparse_vectors_config or None,
            on_disk_payload=request.on_disk_payload,
        )
        return result
