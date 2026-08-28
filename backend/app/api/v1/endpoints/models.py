from fastapi import APIRouter, Depends

from dependencies.services import get_chat_model_registry, get_embedding_registry
from schemes.responses import (
    AvailableModelsResponse,
    ChatModelResponse,
    EmbeddingModelResponse,
)
from services.model_registry import ChatModelRegistry, EmbeddingModelRegistry

router = APIRouter(prefix="/models", tags=["models"])


@router.get("", response_model=AvailableModelsResponse)
async def list_models(
    embedding_registry: EmbeddingModelRegistry = Depends(get_embedding_registry),
    chat_registry: ChatModelRegistry = Depends(get_chat_model_registry),
) -> AvailableModelsResponse:
    """
    ### 선택 가능한 모델 목록 조회

    Response Body:
        embedding: 임베딩 모델 목록
            name: 모델 이름
            provider: 제공자(fastembed/openai 등)
            dimension: 임베딩 차원
        chat: 채팅(생성) 모델 목록
            name: 모델 이름
            provider: 제공자(openai 등)
    """
    embedding = [
        EmbeddingModelResponse(
            name=model.name, provider=model.provider, dimension=model.dimension
        )
        for model in embedding_registry.list_models()
    ]
    chat = [
        ChatModelResponse(name=model.name, provider=model.provider)
        for model in chat_registry.list_models()
    ]
    return AvailableModelsResponse(embedding=embedding, chat=chat)
