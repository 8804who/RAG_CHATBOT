from fastapi import APIRouter, Depends, Path, status
from sqlalchemy.ext.asyncio import AsyncSession

from dependencies.auth import get_current_user
from dependencies.db import get_db_session
from dependencies.services import get_chat_orchestrator
from models import User
from schemes.requests import CreateChatRequest, SendChatMessageRequest
from schemes.responses import ChatMessageResponse, ChatResponse, CitationResponse
from services.agent import AgentChatOrchestrator

router = APIRouter(prefix="/chats", tags=["chat"])


@router.post("", status_code=status.HTTP_201_CREATED, response_model=ChatResponse)
async def create_chat(
    body: CreateChatRequest,
    chat_orchestrator: AgentChatOrchestrator = Depends(get_chat_orchestrator),
    db: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_user),
) -> ChatResponse:
    """
    ### 채팅 시작

    이 채팅에서 사용할 생성 모델을 선택해 세션에 고정 저장한다. 컬렉션은
    선택 사항이며, 지정하지 않으면 에이전트가 매 질의마다 검색 대상 컬렉션을
    스스로 고른다.

    Request Body:
        CreateChatRequest: 채팅 시작 요청
            collection_name: 검색 대상 컬렉션(미지정 시 에이전트가 선택)
            chat_model: 고정 사용할 생성 모델

    Response Body:
        id: 채팅 id
        collection_name: 고정된 컬렉션(없으면 null)
        chat_model: 고정된 생성 모델
        created_at: 생성 시각

    Error Response:
        지정한 컬렉션에 임베딩 모델 매핑이 없을 경우: (400 Bad Request)
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
    chat_orchestrator: AgentChatOrchestrator = Depends(get_chat_orchestrator),
    db: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_user),
) -> ChatMessageResponse:
    """
    ### 채팅 메시지 전송

    질의를 에이전트에 넘긴다. 에이전트는 필요한 도구(문서 검색/계산기/웹
    검색/사용량 조회)를 스스로 선택해 여러 번 호출할 수 있고(멀티스텝),
    문서 검색은 컬렉션이 고정되지 않은 채팅이면 대상 컬렉션도 직접 고른다.
    결과를 메시지로 영속화하고 토큰 사용량을 기록한다(비스트리밍).

    Path Variables:
        chat_id(str): 대상 채팅 id

    Request Body:
        SendChatMessageRequest: 질의 요청
            query: 사용자 질문

    Response Body:
        role: "assistant"
        content: 생성된 답변
        citations: 답변 근거 목록(source_type이 "document"면 chunk_id/document_id/
            collection_name, "web"이면 url이 채워짐)

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
                source_type=citation.source_type,
                title=citation.title,
                snippet=citation.snippet,
                document_id=citation.document_id,
                chunk_id=citation.chunk_id,
                collection_name=citation.collection_name,
                url=citation.url,
            )
            for citation in result.citations
        ],
    )
