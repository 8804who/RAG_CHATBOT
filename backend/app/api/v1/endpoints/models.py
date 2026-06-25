from fastapi import APIRouter, Depends

from dependencies.services import get_embedding_registry
from schemes.responses import AvailableModelsResponse, EmbeddingModelResponse
from services.model_registry import EmbeddingModelRegistry

router = APIRouter(prefix="/models", tags=["models"])


@router.get("", response_model=AvailableModelsResponse)
async def list_models(
    embedding_registry: EmbeddingModelRegistry = Depends(get_embedding_registry),
) -> AvailableModelsResponse:
    """
    ### 선택 가능한 모델 목록 조회

    Response Body:
        embedding: 임베딩 모델 목록
            name: 모델 이름
            provider: 제공자(fastembed/openai 등)
            dimension: 임베딩 차원
    """
    embedding = [
        EmbeddingModelResponse(
            name=model.name, provider=model.provider, dimension=model.dimension
        )
        for model in embedding_registry.list_models()
    ]
    return AvailableModelsResponse(embedding=embedding)
