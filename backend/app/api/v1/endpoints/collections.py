from fastapi import APIRouter, Path, Depends

from dependencies.services import get_qdrant_service
from schemes.requests import CreateQdrantCollectionRequest
from services.vector_db import QdrantService

router = APIRouter(prefix="/collections", tags=["collections"])

@router.get("")
async def get_collections(
    qdrant_service: QdrantService = Depends(get_qdrant_service)
):
    result = await qdrant_service.get_collections()
    return result

@router.post("")
async def create_collection(
    collection_info: CreateQdrantCollectionRequest,
    qdrant_service: QdrantService = Depends(get_qdrant_service)
):
    result = await qdrant_service.create_collections(collection_info=collection_info)
    return result