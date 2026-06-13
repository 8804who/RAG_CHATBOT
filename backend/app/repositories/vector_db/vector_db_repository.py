from abc import ABC, abstractmethod

from schemes.requests import CreateQdrantCollectionRequest


class VectorDBRepository(ABC):
    @abstractmethod
    async def get_collections(self):
        pass

    @abstractmethod
    async def create_collections(self, request: CreateQdrantCollectionRequest):
        pass
