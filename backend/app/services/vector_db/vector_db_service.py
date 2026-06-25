from abc import ABC, abstractmethod

from sqlalchemy.ext.asyncio import AsyncSession

from schemes.dto.qdrant import CollectionDetail, CollectionSummary
from schemes.requests import (
    CreateQdrantCollectionRequest,
    UpdateQdrantCollectionRequest,
)


class VectorDBService(ABC):
    @abstractmethod
    async def get_collections(self) -> list[CollectionSummary]:
        pass

    @abstractmethod
    async def get_collection(self, collection_name: str) -> CollectionDetail:
        pass

    @abstractmethod
    async def create_collections(
        self, db: AsyncSession, collection_info: CreateQdrantCollectionRequest
    ):
        pass

    @abstractmethod
    async def update_collection(
        self, collection_name: str, collection_info: UpdateQdrantCollectionRequest
    ):
        pass

    @abstractmethod
    async def delete_collection(self, db: AsyncSession, collection_name: str):
        pass
