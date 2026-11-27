from fastapi import APIRouter, Depends, Path, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from dependencies.auth import get_current_user
from dependencies.db import get_db_session
from dependencies.services import get_chat_orchestrator
from models import User
from schemes.requests import CreateChatRequest, SendChatMessageRequest
from schemes.responses import (
    ChatHistoryMessageResponse,
    ChatHistoryResponse,
    ChatListResponse,
    ChatMessageResponse,
    ChatResponse,
    ChatSummaryResponse,
    CitationResponse,
)
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


@router.get("", status_code=status.HTTP_200_OK, response_model=ChatListResponse)
async def list_chats(
    chat_orchestrator: AgentChatOrchestrator = Depends(get_chat_orchestrator),
    db: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_user),
) -> ChatListResponse:
    """
    ### 내 채팅 목록 조회

    요청자가 소유한 채팅만 최근 활동순(마지막 메시지 시각, 없으면 생성 시각)으로
    최대 100개 반환한다(페이지네이션 없음).

    Response Body:
        chats: 채팅 목록
            id: 채팅 id
            title: 첫 사용자 질문(공백 정리, 60자 초과 시 "…"), 메시지 없으면 null
            chat_model: 고정된 생성 모델
            collection_name: 고정된 컬렉션(없으면 null)
            created_at: 생성 시각
            last_message_at: 마지막 메시지 시각(없으면 null)

    Error Response:
        로그인하지 않은 경우: (401 Unauthorized)
    """
    chats = await chat_orchestrator.list_chats(db, requester=current_user)
    return ChatListResponse(
        chats=[ChatSummaryResponse.model_validate(chat) for chat in chats]
    )


@router.delete(
    "/{chat_id}", status_code=status.HTTP_204_NO_CONTENT, response_class=Response
)
async def delete_chat(
    chat_id: str = Path(..., min_length=1),
    chat_orchestrator: AgentChatOrchestrator = Depends(get_chat_orchestrator),
    db: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_user),
) -> None:
    """
    ### 채팅 삭제

    채팅과 메시지, 에이전트 대화 메모리(체크포인트)를 함께 삭제한다. 사용량·도구
    호출 로그는 집계용으로 남는다.

    Path Variables:
        chat_id(str): 삭제할 채팅 id

    Response Body:
        NO CONTENT

    Error Response:
        채팅이 존재하지 않을 경우: (404 Not Found)
        다른 사용자의 채팅일 경우: (403 Forbidden)
        같은 채팅의 메시지를 처리 중일 경우: (409 Conflict)
    """
    await chat_orchestrator.delete_chat(db, chat_id=chat_id, requester=current_user)


@router.get(
    "/{chat_id}/messages",
    status_code=status.HTTP_200_OK,
    response_model=ChatHistoryResponse,
)
async def get_messages(
    chat_id: str = Path(..., min_length=1),
    chat_orchestrator: AgentChatOrchestrator = Depends(get_chat_orchestrator),
    db: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_user),
) -> ChatHistoryResponse:
    """
    ### 채팅 이력 조회

    채팅 소유자만 조회할 수 있다. 성공한 턴의 질문·답변만 저장되므로 실패한
    턴은 이력에 없다.

    Path Variables:
        chat_id(str): 대상 채팅 id

    Response Body:
        chat_model: 고정된 생성 모델
        collection_name: 고정된 컬렉션(없으면 null)
        messages: 메시지 목록(오래된 순)
            role: "user" 또는 "assistant"
            content: 본문
            citations: 답변 근거 목록(사용자 메시지는 빈 목록)
            created_at: 저장 시각

    Error Response:
        채팅이 존재하지 않을 경우: (404 Not Found)
        다른 사용자의 채팅일 경우: (403 Forbidden)
    """
    history = await chat_orchestrator.get_messages(
        db, chat_id=chat_id, requester=current_user
    )
    return ChatHistoryResponse(
        chat_model=history.chat_model,
        collection_name=history.collection_name,
        messages=[
            ChatHistoryMessageResponse(
                role=message.role,
                content=message.content,
                citations=[
                    CitationResponse(**citation) for citation in message.citations or []
                ],
                created_at=message.created_at,
            )
            for message in history.messages
        ],
    )


@router.post(
    "/{chat_id}/messages",
    status_code=status.HTTP_200_OK,
    response_model=ChatMessageResponse,
)
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
    결과를 메시지로 영속화하고 토큰 사용량을 기록한다(비스트리밍). 한 턴은
    전부 아니면 전무라, 실패하면 질문도 저장되지 않으므로 그대로 재전송하면 된다.

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
        같은 채팅의 이전 메시지를 처리 중일 경우: (409 Conflict)
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
