import json
import logging
from dataclasses import asdict

from langchain.agents import create_agent
from langchain_core.messages import AIMessage, ToolMessage
from sqlalchemy.ext.asyncio import AsyncSession

from core.constants import AGENT_RECURSION_LIMIT, AGENT_SYSTEM_PROMPT
from exceptions.chat import ChatAccessDeniedError, ChatNotFoundError
from exceptions.document import CollectionMetaNotFoundError
from models import Chat, ChatMessageRole, User
from repositories import ChatRepository, CollectionMetadataRepository, LogRepository
from schemes.dto.chat import Citation, ChatTurnResult
from services.agent.tools import (
    RETRIEVAL_TOOL_NAME,
    WEB_SEARCH_TOOL_NAME,
    build_calculator_tool,
    build_retrieval_tool,
    build_usage_stats_tool,
    build_web_search_tool,
)
from services.model_registry import ChatModelRegistry
from services.retrieval import RetrievalService
from services.usage import UsageStatsService

logger = logging.getLogger(__name__)

_SNIPPET_LENGTH = 300


class AgentChatOrchestrator:
    """
    RAG 채팅 한 턴을 LangGraph 기반 에이전트로 조립한다.

    고정 파이프라인(검색→생성) 대신, 요청마다 도구(문서 검색/계산기/웹 검색/
    사용량 조회)를 구성해 LangChain의 create_agent 루프에 맡긴다. 에이전트가
    스스로 도구 호출 여부·횟수·검색 대상 컬렉션을 결정한다(멀티스텝 가능).
    provider/모델 세부사항은 알지 못한다(레지스트리 뒤로 숨겨짐).
    """

    def __init__(
        self,
        chat_repository: ChatRepository,
        chat_model_registry: ChatModelRegistry,
        collection_meta_repository: CollectionMetadataRepository,
        retrieval_service: RetrievalService,
        usage_stats_service: UsageStatsService,
        log_repository: LogRepository,
        langfuse_handler,
    ) -> None:
        self._chats = chat_repository
        self._chat_model_registry = chat_model_registry
        self._collection_meta_repository = collection_meta_repository
        self._retrieval = retrieval_service
        self._usage_stats = usage_stats_service
        self._log_repository = log_repository
        self._langfuse_handler = langfuse_handler

    async def create_chat(
        self,
        db: AsyncSession,
        *,
        collection_name: str | None,
        chat_model: str,
        owner_id: int | None,
    ) -> Chat:
        """
        채팅 시작(채팅 모델 유효성 검증 + 선택적 컬렉션 고정)

        collection_name이 주어지면 기존과 동일하게 해당 컬렉션에 검색을
        제한한다. None이면 에이전트가 매 질의마다 검색 대상 컬렉션을 고른다.

        Parameters:
            db(AsyncSession): DB 세션
            collection_name(str | None): 검색 대상 컬렉션(미지정 시 에이전트가 선택)
            chat_model(str): 이 채팅에서 고정 사용할 생성 모델
            owner_id(int | None): 채팅 소유자 user id

        Returns:
            Chat: 생성된 채팅 세션
        """
        self._chat_model_registry.get_info(chat_model)  # 미등록이면 예외

        if collection_name is not None:
            meta = await self._collection_meta_repository.get_collection_metadata(
                db, collection_name
            )
            if meta is None:
                raise CollectionMetaNotFoundError(
                    message=f"collection '{collection_name}' has no embedding mapping",
                    code_path="agent_chat_orchestrator-create_chat-error",
                )

        chat = await self._chats.create_chat(
            db,
            collection_name=collection_name,
            chat_model=chat_model,
            owner_id=owner_id,
        )
        logger.info(
            "채팅 생성 완료: chat_id=%s, collection=%s, chat_model=%s, owner_id=%s",
            chat.id,
            collection_name,
            chat_model,
            owner_id,
        )
        return chat

    async def send_message(
        self, db: AsyncSession, *, chat_id: str, query: str, requester: User
    ) -> ChatTurnResult:
        """
        한 사용자 질의에 대한 답변을 에이전트로 생성한다

        (도구 구성 → 에이전트 실행(멀티스텝 가능) → 메시지 영속화 → 사용량 기록)

        Parameters:
            db(AsyncSession): DB 세션
            chat_id(str): 채팅 세션 id
            query(str): 사용자 질문
            requester(User): 요청 사용자(소유권 검증용)

        Returns:
            ChatTurnResult: 답변 + 인용 목록
        """
        chat = await self._chats.get_chat(db, chat_id)
        if chat is None:
            raise ChatNotFoundError(
                message=f"chat '{chat_id}' not found",
                code_path="agent_chat_orchestrator-send_message-error",
            )
        if chat.owner_id != requester.id:
            raise ChatAccessDeniedError(
                message=f"user '{requester.id}' has no access to chat '{chat_id}'",
                code_path="agent_chat_orchestrator-send_message-error",
            )

        await self._chats.add_message(
            db, chat_id=chat_id, role=ChatMessageRole.USER, content=query
        )

        logger.info(
            "메시지 처리 시작: chat_id=%s, requester=%s, collection=%s, chat_model=%s",
            chat_id,
            requester.email,
            chat.collection_name,
            chat.chat_model,
        )

        tools = [
            await build_retrieval_tool(
                db,
                self._retrieval,
                self._collection_meta_repository,
                chat.collection_name,
            ),
            build_calculator_tool(),
            build_usage_stats_tool(db, self._usage_stats, requester.id),
        ]
        web_search_tool = build_web_search_tool()
        if web_search_tool is not None:
            tools.append(web_search_tool)

        model = self._chat_model_registry.resolve(chat.chat_model)
        graph = create_agent(
            model=model, tools=tools, system_prompt=AGENT_SYSTEM_PROMPT
        )

        run_config = {
            "callbacks": [self._langfuse_handler] if self._langfuse_handler else [],
            "recursion_limit": AGENT_RECURSION_LIMIT,
            "metadata": {
                "langfuse_session_id": chat_id,
                "langfuse_user_id": str(requester.id),
            },
        }

        try:
            result = await graph.ainvoke(
                {"messages": [{"role": "user", "content": query}]}, config=run_config
            )
        except Exception:
            logger.exception(
                "메시지 처리 실패: chat_id=%s, requester=%s",
                chat_id,
                requester.email,
            )
            raise

        messages = result["messages"]
        answer_content = ""
        input_tokens = 0
        output_tokens = 0
        reasoning_tokens = 0
        for message in messages:
            if not isinstance(message, AIMessage):
                continue
            if message.content:
                answer_content = message.content
            usage = message.usage_metadata
            if usage:
                input_tokens += usage.get("input_tokens", 0) or 0
                output_tokens += usage.get("output_tokens", 0) or 0
                reasoning_tokens += (usage.get("output_token_details") or {}).get(
                    "reasoning", 0
                ) or 0

        citations = _extract_citations(messages)

        await self._chats.add_message(
            db,
            chat_id=chat_id,
            role=ChatMessageRole.ASSISTANT,
            content=answer_content,
            citations=[asdict(citation) for citation in citations],
        )

        await self._log_repository.create_chat_usage_log(
            db,
            model=chat.chat_model,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            reasoning_tokens=reasoning_tokens,
            requester_id=requester.id,
            requester_email=requester.email,
            collection_name=chat.collection_name,
            conversation_id=chat.id,
        )

        logger.info(
            "메시지 처리 완료: chat_id=%s, citation_count=%d, input_tokens=%d, output_tokens=%d",
            chat_id,
            len(citations),
            input_tokens,
            output_tokens,
        )

        return ChatTurnResult(content=answer_content, citations=citations)


def _extract_citations(messages: list) -> list[Citation]:
    """
    도구(ToolMessage)의 JSON 결과를 파싱해 인용 목록으로 변환

    문서 검색 도구와 웹 검색 도구 결과를 모두 인용으로 취급하며, 같은
    출처(chunk_id 또는 url)가 여러 번 검색돼도 한 번만 남긴다.
    """
    seen: dict[str, Citation] = {}
    for message in messages:
        if not isinstance(message, ToolMessage):
            continue
        try:
            payload = json.loads(message.content)
        except (TypeError, ValueError):
            continue

        if message.name == RETRIEVAL_TOOL_NAME:
            for item in payload.get("results", []):
                chunk_id = item.get("chunk_id")
                if not chunk_id or chunk_id in seen:
                    continue
                seen[chunk_id] = Citation(
                    source_type="document",
                    title=item.get("filename", "(unknown)"),
                    snippet=item.get("snippet", ""),
                    document_id=item.get("document_id"),
                    chunk_id=chunk_id,
                    collection_name=item.get("collection_name"),
                )
        elif message.name == WEB_SEARCH_TOOL_NAME:
            for item in payload.get("results", []):
                url = item.get("url")
                if not url or url in seen:
                    continue
                seen[url] = Citation(
                    source_type="web",
                    title=item.get("title") or url,
                    snippet=(item.get("content") or "")[:_SNIPPET_LENGTH],
                    url=url,
                )

    return list(seen.values())
