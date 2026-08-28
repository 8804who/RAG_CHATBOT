from fastapi import APIRouter, Depends, Path, status
from sqlalchemy.ext.asyncio import AsyncSession

from dependencies.auth import get_current_user
from dependencies.db import get_db_session
from dependencies.services import get_chat_orchestrator
from models import User
from schemes.requests import CreateChatRequest, SendChatMessageRequest
from schemes.responses import ChatMessageResponse, ChatResponse, CitationResponse
from services.chat import ChatOrchestrator

router = APIRouter(prefix="/chats", tags=["chat"])


@router.post("", status_code=status.HTTP_201_CREATED, response_model=ChatResponse)
async def create_chat(
    body: CreateChatRequest,
    chat_orchestrator: ChatOrchestrator = Depends(get_chat_orchestrator),
    db: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_user),
) -> ChatResponse:
    """
    ### 채팅 시작

    이 채팅에서 사용할 컬렉션·생성 모델을 선택해 세션에 고정 저장한다.

    Request Body:
        CreateChatRequest: 채팅 시작 요청
            collection_name: 검색 대상 컬렉션
            chat_model: 고정 사용할 생성 모델

    Response Body:
        id: 채팅 id
        collection_name: 고정된 컬렉션
        chat_model: 고정된 생성 모델
        created_at: 생성 시각

    Error Response:
        컬렉션에 임베딩 모델 매핑이 없을 경우: (400 Bad Request)
        지원하지 않는 채팅 모델일 경우: (400 Bad Request)
    """
    chat = await chat_orchestrator.create_chat(
        db,
        collection_name=body.collection_name,
        chat_model=body.chat_model,
        owner_id=current_user.id,
    )
    return ChatResponse.model_validate(chat)


@router.post("/{chat_id}/messages", response_model=ChatMessageResponse)
async def send_message(
    body: SendChatMessageRequest,
    chat_id: str = Path(..., min_length=1),
    chat_orchestrator: ChatOrchestrator = Depends(get_chat_orchestrator),
    db: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_user),
) -> ChatMessageResponse:
    """
    ### 채팅 메시지 전송

    질의 → 컬렉션 고정 임베딩 모델로 하이브리드 검색 → 채팅에 고정된 모델로
    답변 생성(비스트리밍). 검색·생성 결과를 메시지로 영속화하고 토큰 사용량을
    기록한다.

    Path Variables:
        chat_id(str): 대상 채팅 id

    Request Body:
        SendChatMessageRequest: 질의 요청
            query: 사용자 질문

    Response Body:
        role: "assistant"
        content: 생성된 답변
        citations: 답변 근거 목록(chunk_id, document_id, filename, snippet)

    Error Response:
        채팅이 존재하지 않을 경우: (404 Not Found)
        다른 사용자의 채팅일 경우: (403 Forbidden)
    """
    result = await chat_orchestrator.send_message(
        db, chat_id=chat_id, query=body.query, requester=current_user
    )
    return ChatMessageResponse(
        role="assistant",
        content=result.content,
        citations=[
            CitationResponse(
                chunk_id=citation.chunk_id,
                document_id=citation.document_id,
                filename=citation.filename,
                snippet=citation.snippet,
            )
            for citation in result.citations
        ],
    )
