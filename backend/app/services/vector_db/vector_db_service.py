from abc import ABC, abstractmethod

from schemes.requests import CreateQdrantCollectionRequest


class VectorDBService(ABC):
    @abstractmethod
    async def get_collections(self):
        pass

    @abstractmethod
    async def create_collections(self, collection_info: CreateQdrantCollectionRequest):
        pass
