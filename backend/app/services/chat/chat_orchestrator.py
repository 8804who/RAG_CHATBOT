from dataclasses import asdict

from sqlalchemy.ext.asyncio import AsyncSession

from exceptions.chat import ChatAccessDeniedError, ChatNotFoundError
from exceptions.document import CollectionMetaNotFoundError
from models import Chat, ChatMessageRole, User
from repositories import CollectionMetadataRepository, ChatRepository, LogRepository
from schemes.dto.chat import Citation, ChatTurnResult
from services.generation import GenerationService
from services.model_registry import ChatModelRegistry
from services.retrieval import RetrievalService

_CITATION_SNIPPET_LENGTH = 300


class ChatOrchestrator:
    """
    RAG 채팅 한 턴을 조립한다.

    검색→생성을 순서대로 호출하고, 사용자/어시스턴트 메시지를 영속화하며
    사용량을 기록한다. provider/모델 세부사항은 알지 못한다(레지스트리 뒤로
    숨겨짐).
    """

    def __init__(
        self,
        chat_repository: ChatRepository,
        chat_model_registry: ChatModelRegistry,
        collection_meta_repository: CollectionMetadataRepository,
        retrieval_service: RetrievalService,
        generation_service: GenerationService,
        log_repository: LogRepository,
    ) -> None:
        self._chats = chat_repository
        self._chat_model_registry = chat_model_registry
        self._collection_meta_repository = collection_meta_repository
        self._retrieval = retrieval_service
        self._generation = generation_service
        self._log_repository = log_repository

    async def create_chat(
        self,
        db: AsyncSession,
        *,
        collection_name: str,
        chat_model: str,
        owner_id: int | None,
    ) -> Chat:
        """
        채팅 시작(컬렉션·채팅 모델 유효성 검증 후 고정)

        Parameters:
            db(AsyncSession): DB 세션
            collection_name(str): 검색 대상 컬렉션
            chat_model(str): 이 채팅에서 고정 사용할 생성 모델
            owner_id(int | None): 채팅 소유자 user id

        Returns:
            Chat: 생성된 채팅 세션
        """
        self._chat_model_registry.get_info(chat_model)  # 미등록이면 예외

        meta = await self._collection_meta_repository.get_collection_metadata(
            db, collection_name
        )
        if meta is None:
            raise CollectionMetaNotFoundError(
                message=f"collection '{collection_name}' has no embedding mapping",
                code_path="chat_orchestrator-create_chat-error",
            )

        return await self._chats.create_chat(
            db,
            collection_name=collection_name,
            chat_model=chat_model,
            owner_id=owner_id,
        )

    async def send_message(
        self, db: AsyncSession, *, chat_id: str, query: str, requester: User
    ) -> ChatTurnResult:
        """
        한 사용자 질의에 대한 답변을 생성한다(검색 → 생성 → 영속화 → 사용량 기록)

        Parameters:
            db(AsyncSession): DB 세션
            chat_id(str): 채팅 세션 id(collection·chat_model 보유)
            query(str): 사용자 질문
            requester(User): 요청 사용자(소유권 검증용)

        Returns:
            ChatTurnResult: 답변 + 인용 목록
        """
        chat = await self._chats.get_chat(db, chat_id)
        if chat is None:
            raise ChatNotFoundError(
                message=f"chat '{chat_id}' not found",
                code_path="chat_orchestrator-send_message-error",
            )
        if chat.owner_id != requester.id:
            raise ChatAccessDeniedError(
                message=f"user '{requester.id}' has no access to chat '{chat_id}'",
                code_path="chat_orchestrator-send_message-error",
            )

        await self._chats.add_message(
            db, chat_id=chat_id, role=ChatMessageRole.USER, content=query
        )

        chunks = await self._retrieval.retrieve(db, chat.collection_name, query)
        answer = await self._generation.answer(chat.chat_model, query, chunks)

        citations = [
            Citation(
                chunk_id=chunk.chunk_id,
                document_id=chunk.document_id,
                filename=chunk.filename,
                snippet=chunk.text[:_CITATION_SNIPPET_LENGTH],
            )
            for chunk in chunks
        ]

        await self._chats.add_message(
            db,
            chat_id=chat_id,
            role=ChatMessageRole.ASSISTANT,
            content=answer.content,
            citations=[asdict(citation) for citation in citations],
        )

        await self._log_repository.create_chat_usage_log(
            db,
            model=chat.chat_model,
            input_tokens=answer.input_tokens,
            output_tokens=answer.output_tokens,
            reasoning_tokens=answer.reasoning_tokens,
            requester_id=requester.id,
            requester_email=requester.email,
            collection_name=chat.collection_name,
            conversation_id=chat.id,
        )

        return ChatTurnResult(content=answer.content, citations=citations)
