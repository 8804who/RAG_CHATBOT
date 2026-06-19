from abc import ABC, abstractmethod

from schemes.dto.qdrant import CollectionDetail, CollectionSummary
from schemes.requests import (
    CreateQdrantCollectionRequest,
    UpdateQdrantCollectionRequest,
)


class VectorDBRepository(ABC):
    @abstractmethod
    async def get_collections(self) -> list[CollectionSummary]:
        pass

    @abstractmethod
    async def get_collection(self, collection_name: str) -> CollectionDetail:
        pass

    @abstractmethod
    async def create_collections(self, request: CreateQdrantCollectionRequest):
        pass

    @abstractmethod
    async def update_collection(
        self, collection_name: str, request: UpdateQdrantCollectionRequest
    ):
        pass

    @abstractmethod
    async def delete_collection(self, collection_name: str):
        pass
