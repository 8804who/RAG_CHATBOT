import asyncio
import json
import logging
import sys
from collections.abc import AsyncGenerator, AsyncIterator, Coroutine
from contextlib import aclosing
from dataclasses import asdict, dataclass, replace
from typing import Any

import anyio
from langchain.agents import create_agent
from langchain.agents.middleware import SummarizationMiddleware
from langchain_core.callbacks import UsageMetadataCallbackHandler
from langchain_core.messages import (
    AIMessage,
    AnyMessage,
    HumanMessage,
    RemoveMessage,
    ToolMessage,
)
from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.graph.message import REMOVE_ALL_MESSAGES
from langgraph.graph.state import CompiledStateGraph
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from clients import RedisClient
from core.constants import (
    AGENT_RECURSION_LIMIT,
    AGENT_SYSTEM_PROMPT,
    CHAT_SUMMARY_KEEP_MESSAGES,
    CHAT_SUMMARY_MODEL,
    CHAT_LIST_LIMIT,
    CHAT_STREAM_EVENT_DONE,
    CHAT_STREAM_EVENT_ERROR,
    CHAT_STREAM_EVENT_TOKEN,
    CHAT_STREAM_MODEL_NODE,
    CHAT_SUMMARY_TRIGGER_TOKENS,
    CHAT_TITLE_ELLIPSIS,
    CHAT_TITLE_MAX_LENGTH,
    CHAT_TURN_LOCK_KEY_PREFIX,
    CHAT_TURN_LOCK_TTL_SECONDS,
    CHAT_TURN_TIMEOUT_SECONDS,
    GENERIC_ERROR_MESSAGE,
)
from exceptions.base import AppException
from exceptions.chat import (
    ChatAccessDeniedError,
    ChatNotFoundError,
    ChatTurnInProgressError,
)
from exceptions.document import CollectionMetaNotFoundError
from models import Chat, User
from repositories import ChatRepository, CollectionMetadataRepository, LogRepository
from schemes.dto.chat import (
    ChatHistory,
    ChatStreamEvent,
    ChatSummary,
    ChatTurnResult,
    Citation,
    TurnUsage,
)
from services.agent.tools import (
    ARXIV_SEARCH_TOOL_NAME,
    RETRIEVAL_TOOL_NAME,
    WEB_SEARCH_TOOL_NAME,
    build_arxiv_search_tool,
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


@dataclass(slots=True)
class _AgentTurn:
    """
    잠금 안에서 실행하는 에이전트 한 턴의 실행 문맥(비스트리밍·스트리밍 공용)
    """

    chat: Chat
    query: str
    requester: User
    graph: CompiledStateGraph
    run_config: dict
    usage_handler: UsageMetadataCallbackHandler
    before: list[AnyMessage]

    @property
    def input(self) -> dict:
        """이번 턴 그래프 입력(현재 질문만, 이전 메시지는 체크포인터가 복원)"""
        return {"messages": [HumanMessage(content=self.query)]}


class AgentChatOrchestrator:
    """
    RAG 채팅 한 턴을 LangGraph 기반 에이전트로 조립한다.

    고정 파이프라인(검색→생성) 대신, 요청마다 도구(문서 검색/계산기/웹 검색/
    사용량 조회)를 구성해 LangChain의 create_agent 루프에 맡긴다. 에이전트가
    스스로 도구 호출 여부·횟수·검색 대상 컬렉션을 결정한다(멀티스텝 가능).
    provider/모델 세부사항은 알지 못한다(레지스트리 뒤로 숨겨짐).

    멀티턴: 체크포인터가 chat_id를 thread_id로 에이전트 상태(이전 메시지·도구 결과)를
    저장/복원하고, 길어지면 SummarizationMiddleware가 오래된 메시지를 요약으로 대체한다.
    한 턴은 전부 아니면 전무(D-016): 실패하면 스레드를 턴 시작 전으로 되돌리고
    chat_messages에는 성공한 턴만 저장한다. 채팅당 동시 턴은 Redis 잠금으로 1개.
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
        checkpointer: BaseCheckpointSaver,
        redis_client: RedisClient,
        session_factory: async_sessionmaker[AsyncSession],
    ) -> None:
        self._chats = chat_repository
        self._chat_model_registry = chat_model_registry
        self._collection_meta_repository = collection_meta_repository
        self._retrieval = retrieval_service
        self._usage_stats = usage_stats_service
        self._log_repository = log_repository
        self._langfuse_handler = langfuse_handler
        self._checkpointer = checkpointer
        self._redis = redis_client
        self._session_factory = session_factory

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

    async def get_messages(
        self, db: AsyncSession, *, chat_id: str, requester: User
    ) -> ChatHistory:
        """
        채팅 이력 조회(소유자만, 오래된 순)

        Parameters:
            db(AsyncSession): DB 세션
            chat_id(str): 채팅 세션 id
            requester(User): 요청 사용자(소유권 검증용)

        Returns:
            ChatHistory: 채팅 모델·컬렉션 + 메시지 목록
        """
        chat = await self._get_owned_chat(db, chat_id, requester, "get_messages")
        messages = await self._chats.list_messages(db, chat_id)
        return ChatHistory(
            chat_model=chat.chat_model,
            collection_name=chat.collection_name,
            messages=messages,
        )

    async def list_chats(
        self, db: AsyncSession, *, requester: User
    ) -> list[ChatSummary]:
        """
        요청자 소유 채팅 목록 조회(최근 활동순, 최대 CHAT_LIST_LIMIT개)

        Parameters:
            db(AsyncSession): DB 세션
            requester(User): 요청 사용자(소유자 필터)

        Returns:
            list[ChatSummary]: 채팅 요약 목록(제목은 상한 초과 시 말줄임)
        """
        chats = await self._chats.list_chats(
            db, owner_id=requester.id, limit=CHAT_LIST_LIMIT
        )
        return [replace(chat, title=_truncate_title(chat.title)) for chat in chats]

    async def delete_chat(
        self, db: AsyncSession, *, chat_id: str, requester: User
    ) -> None:
        """
        채팅 삭제(소유권 검증 → 턴 잠금 → 존재 재확인 → 체크포인트 스레드 삭제 → chats 행 삭제 → 잠금 해제)

        진행 중인 턴과 겹치지 않도록 send_message와 같은 잠금을 잡는다. 스레드를 먼저
        지워, 중간에 실패해도 chats 행이 남아 같은 요청으로 끝까지 재시도할 수 있다.

        Parameters:
            db(AsyncSession): DB 세션
            chat_id(str): 삭제할 채팅 id
            requester(User): 요청 사용자(소유권 검증용)
        """
        await self._get_owned_chat(db, chat_id, requester, "delete_chat")
        # 조회 트랜잭션이 Redis·체크포인트 호출 동안 커넥션을 붙잡지 않도록 종료
        await db.commit()

        lock_key = await self._acquire_turn_lock(chat_id, requester, "delete_chat")
        try:
            # 잠금 대기 중 다른 삭제가 끝났을 수 있으므로 잠금 안에서 재확인(404)
            await self._get_owned_chat(db, chat_id, requester, "delete_chat")
            await db.commit()
            await self._checkpointer.adelete_thread(chat_id)
            await self._chats.delete_chat(db, chat_id)
        finally:
            await self._redis.delete(lock_key)
        logger.info("채팅 삭제 완료: chat_id=%s, owner_id=%s", chat_id, requester.id)

    async def send_message(
        self, db: AsyncSession, *, chat_id: str, query: str, requester: User
    ) -> ChatTurnResult:
        """
        한 사용자 질의에 대한 답변을 에이전트로 생성한다

        (소유권 검증 → 채팅 잠금 → 존재 재확인 → 에이전트 실행(실패 시 스레드 롤백) →
        성공 턴만 메시지·사용량 영속화 → 체크포인트 정리 → 잠금 해제)

        Parameters:
            db(AsyncSession): DB 세션
            chat_id(str): 채팅 세션 id
            query(str): 사용자 질문
            requester(User): 요청 사용자(소유권 검증용)

        Returns:
            ChatTurnResult: 답변 + 인용 목록
        """
        chat, lock_key = await self._lock_owned_chat(
            db, chat_id, requester, "send_message"
        )
        try:
            return await self._run_turn(db, chat, query, requester)
        finally:
            # ponytail: 소유 토큰 비교 없이 삭제. 턴 상한(asyncio.timeout) < TTL이라
            # 실행 중 만료돼 남의 잠금을 지울 일은 없다.
            await self._redis.delete(lock_key)

    async def stream_message(
        self, db: AsyncSession, *, chat_id: str, query: str, requester: User
    ) -> AsyncIterator[ChatStreamEvent]:
        """
        한 사용자 질의의 답변을 토큰 단위로 스트리밍하는 이벤트 스트림 준비

        소유권 검증·잠금은 여기서 끝내 404/403/409가 스트림 시작 전에 예외로 나간다.
        반환된 스트림은 token* → done|error 1회 순서로 이벤트를 내고, 잠금을 넘겨받아
        종료 시(정상·오류·취소) 직접 해제한다.

        Parameters:
            db(AsyncSession): DB 세션(스트림 종료까지 열려 있어야 함)
            chat_id(str): 채팅 세션 id
            query(str): 사용자 질문
            requester(User): 요청 사용자(소유권 검증용)

        Returns:
            AsyncIterator[ChatStreamEvent]: 턴 이벤트 스트림
        """
        chat, lock_key = await self._lock_owned_chat(
            db, chat_id, requester, "stream_message"
        )
        # ponytail: 잠금 해제는 스트림의 finally 담당. 첫 chunk 전에 클라이언트가 끊겨
        # 스트림이 시작조차 안 되면 TTL(CHAT_TURN_LOCK_TTL_SECONDS) 만료까지 잠금이 남는다.
        return self._stream_turn(db, chat, query, requester, lock_key)

    async def _lock_owned_chat(
        self, db: AsyncSession, chat_id: str, requester: User, action: str
    ) -> tuple[Chat, str]:
        """
        소유권 검증 → 턴 잠금 → 잠금 안에서 존재 재확인(실패 시 잠금 해제 후 예외)

        Parameters:
            db(AsyncSession): DB 세션
            chat_id(str): 채팅 세션 id
            requester(User): 요청 사용자
            action(str): code_path에 남길 호출 함수명

        Returns:
            tuple[Chat, str]: 재확인한 채팅, 획득한 잠금 키(호출자가 해제)
        """
        await self._get_owned_chat(db, chat_id, requester, action)
        # LLM 루프 동안 요청 세션이 idle-in-transaction으로 커넥션을 붙잡지 않도록
        # 읽기 트랜잭션을 여기서 끝낸다(expire_on_commit=False라 객체는 그대로 사용).
        await db.commit()

        lock_key = await self._acquire_turn_lock(chat_id, requester, action)
        try:
            # 잠금 대기 중 채팅이 삭제됐다면 LLM 턴 대신 404(FK 위반 500 방지)
            chat = await self._get_owned_chat(db, chat_id, requester, action)
            await db.commit()
        except BaseException:
            await self._redis.delete(lock_key)
            raise
        return chat, lock_key

    async def _acquire_turn_lock(
        self, chat_id: str, requester: User, action: str
    ) -> str:
        """
        채팅별 턴 잠금 획득(이미 잡혀 있으면 409)

        Parameters:
            chat_id(str): 채팅 id
            requester(User): 요청 사용자(잠금 값)
            action(str): code_path에 남길 호출 함수명

        Returns:
            str: 획득한 잠금 키(finally에서 해제용)
        """
        lock_key = f"{CHAT_TURN_LOCK_KEY_PREFIX}{chat_id}"
        if not await self._redis.set_if_absent(
            lock_key, str(requester.id), ex=CHAT_TURN_LOCK_TTL_SECONDS
        ):
            logger.warning("채팅 턴 중복 요청: chat_id=%s, action=%s", chat_id, action)
            raise ChatTurnInProgressError(
                message=ChatTurnInProgressError.response_message,
                code_path=f"agent_chat_orchestrator-{action}-error",
            )
        return lock_key

    async def _get_owned_chat(
        self, db: AsyncSession, chat_id: str, requester: User, action: str
    ) -> Chat:
        """
        채팅 조회 + 소유권 검증(없으면 404, 남의 채팅이면 403)

        Parameters:
            db(AsyncSession): DB 세션
            chat_id(str): 채팅 세션 id
            requester(User): 요청 사용자
            action(str): code_path에 남길 호출 함수명

        Returns:
            Chat: 요청자가 소유한 채팅
        """
        code_path = f"agent_chat_orchestrator-{action}-error"
        chat = await self._chats.get_chat(db, chat_id)
        # 클라이언트 메시지는 일반 문구만, id는 로그에만 남긴다(KI-058).
        if chat is None:
            logger.warning(
                "채팅 조회 실패: chat_id=%s, requester_id=%s", chat_id, requester.id
            )
            raise ChatNotFoundError(
                message=ChatNotFoundError.response_message, code_path=code_path
            )
        if chat.owner_id != requester.id:
            logger.warning(
                "채팅 접근 거부: chat_id=%s, requester_id=%s", chat_id, requester.id
            )
            raise ChatAccessDeniedError(
                message=ChatAccessDeniedError.response_message, code_path=code_path
            )
        return chat

    async def _run_turn(
        self, db: AsyncSession, chat: Chat, query: str, requester: User
    ) -> ChatTurnResult:
        """
        잠금을 잡은 상태에서 에이전트 한 턴 실행 + 성공 시 영속화

        Parameters:
            db(AsyncSession): 요청 DB 세션(실행 후 영속화에만 사용)
            chat(Chat): 대상 채팅
            query(str): 사용자 질문
            requester(User): 요청 사용자

        Returns:
            ChatTurnResult: 답변 + 인용 목록
        """
        turn = await self._start_turn(chat, query, requester)
        try:
            async with asyncio.timeout(CHAT_TURN_TIMEOUT_SECONDS):
                result = await turn.graph.ainvoke(
                    turn.input, config=turn.run_config, durability="exit"
                )
        except BaseException:
            await self._abort_turn(turn)
            raise
        return await self._finish_turn(db, turn, result["messages"])

    async def _stream_turn(
        self,
        db: AsyncSession,
        chat: Chat,
        query: str,
        requester: User,
        lock_key: str,
    ) -> AsyncIterator[ChatStreamEvent]:
        """
        잠금을 넘겨받아 스트리밍 턴을 실행하고 종료 시 잠금 해제

        Parameters:
            db(AsyncSession): 요청 DB 세션
            chat(Chat): 대상 채팅
            query(str): 사용자 질문
            requester(User): 요청 사용자
            lock_key(str): 이미 획득한 턴 잠금 키

        Returns:
            AsyncIterator[ChatStreamEvent]: 턴 이벤트 스트림
        """
        try:
            # 바깥이 닫히면(클라이언트 끊김) 안쪽 스트림도 닫아 롤백이 잠금 해제보다 먼저 돈다
            async with aclosing(
                self._stream_events(db, chat, query, requester)
            ) as events:
                async for event in events:
                    yield event
        finally:
            await _shielded(self._redis.delete(lock_key))

    async def _stream_events(
        self, db: AsyncSession, chat: Chat, query: str, requester: User
    ) -> AsyncIterator[ChatStreamEvent]:
        """
        에이전트를 stream_mode="messages"로 실행해 답변 토큰 → 영속화 → done/error 이벤트 생성

        실패하면 스레드를 턴 시작 전으로 롤백하고 error 1건(AppException이면 그 message,
        아니면 일반 문구)으로 끝낸다. 취소·종료(BaseException)는 롤백 후 그대로 전파한다.
        턴 상한은 그래프·상태 조회 대기 시간에 걸린다(클라이언트로 보내는 시간 제외).

        Parameters:
            db(AsyncSession): 요청 DB 세션(실행 후 영속화에만 사용)
            chat(Chat): 대상 채팅
            query(str): 사용자 질문
            requester(User): 요청 사용자

        Returns:
            AsyncIterator[ChatStreamEvent]: token* → done|error 이벤트
        """
        turn = await self._start_turn(chat, query, requester)
        deadline = asyncio.get_running_loop().time() + CHAT_TURN_TIMEOUT_SECONDS
        stream = turn.graph.astream(
            turn.input,
            config=turn.run_config,
            stream_mode="messages",
            durability="exit",
        )
        try:
            while (item := await _next_before(stream, deadline)) is not None:
                if token := _answer_token(*item):
                    yield ChatStreamEvent(event=CHAT_STREAM_EVENT_TOKEN, content=token)
            async with asyncio.timeout_at(deadline):
                state = await turn.graph.aget_state(turn.run_config)
            result = await self._finish_turn(db, turn, state.values.get("messages", []))
        except AppException as exc:
            await self._abort_stream(turn, stream)
            yield ChatStreamEvent(event=CHAT_STREAM_EVENT_ERROR, content=exc.message)
        except Exception:
            await self._abort_stream(turn, stream)
            yield ChatStreamEvent(
                event=CHAT_STREAM_EVENT_ERROR, content=GENERIC_ERROR_MESSAGE
            )
        except BaseException:
            await self._abort_stream(turn, stream)
            raise
        else:
            yield ChatStreamEvent(event=CHAT_STREAM_EVENT_DONE, result=result)

    async def _start_turn(self, chat: Chat, query: str, requester: User) -> _AgentTurn:
        """
        턴 실행 문맥 준비(그래프·usage 집계기·실행 설정·턴 시작 전 스레드 메시지)

        Parameters:
            chat(Chat): 대상 채팅
            query(str): 사용자 질문
            requester(User): 요청 사용자

        Returns:
            _AgentTurn: 턴 실행 문맥
        """
        logger.info(
            "메시지 처리 시작: chat_id=%s, requester_id=%s, collection=%s, chat_model=%s",
            chat.id,
            requester.id,
            chat.collection_name,
            chat.chat_model,
        )
        graph = await self._build_graph(chat, requester)
        usage_handler = UsageMetadataCallbackHandler()
        run_config = self._run_config(chat.id, requester, usage_handler)
        before = (await graph.aget_state(run_config)).values.get("messages", [])
        return _AgentTurn(
            chat=chat,
            query=query,
            requester=requester,
            graph=graph,
            run_config=run_config,
            usage_handler=usage_handler,
            before=before,
        )

    async def _abort_turn(self, turn: _AgentTurn) -> None:
        """
        실패 턴 기록 + 스레드 롤백(except 블록 안에서 호출)

        CancelledError(배포 SIGTERM·클라이언트 끊김)도 롤백 대상이다. 롤백 자체가
        다시 취소되지 않도록 shield로 감싸 끝까지 실행한다. 취소·종료는 일상적인
        끊김이라 traceback 없이 WARNING, 그 외 실패는 ERROR + traceback으로 기록한다.

        Parameters:
            turn(_AgentTurn): 실패한 턴 문맥
        """
        if isinstance(sys.exception(), asyncio.CancelledError | GeneratorExit):
            logger.warning(
                "메시지 처리 중단(취소·연결 끊김): chat_id=%s, requester_id=%s",
                turn.chat.id,
                turn.requester.id,
            )
        else:
            logger.exception(
                "메시지 처리 실패: chat_id=%s, requester_id=%s",
                turn.chat.id,
                turn.requester.id,
            )
        await _shielded(self._rollback_thread(turn.graph, turn.run_config, turn.before))

    async def _abort_stream(
        self, turn: _AgentTurn, stream: AsyncGenerator[Any, None]
    ) -> None:
        """
        스트리밍 실패 턴 정리(그래프 스트림 종료 → 스레드 롤백)

        중단된 astream이 닫히며 체크포인트를 쓸 수 있어, 롤백보다 먼저 닫는다.

        Parameters:
            turn(_AgentTurn): 실패한 턴 문맥
            stream(AsyncGenerator[Any, None]): 그래프 astream 제너레이터
        """
        await _shielded(stream.aclose())
        await self._abort_turn(turn)

    async def _finish_turn(
        self, db: AsyncSession, turn: _AgentTurn, messages: list[AnyMessage]
    ) -> ChatTurnResult:
        """
        성공한 턴 결과 계산 + 메시지·사용량 영속화 + 체크포인트 정리

        Parameters:
            db(AsyncSession): 요청 DB 세션
            turn(_AgentTurn): 턴 문맥
            messages(list[AnyMessage]): 실행 후 스레드 메시지

        Returns:
            ChatTurnResult: 답변 + 인용 목록
        """
        chat = turn.chat
        turn_messages = _new_messages(messages, turn.before)
        answer = _final_answer(turn_messages)
        citations = _extract_citations(turn_messages)
        tool_calls = _tool_calls(turn_messages)
        usage = _sum_usage(turn.usage_handler)

        await self._chats.add_turn_messages(
            db,
            chat_id=chat.id,
            query=turn.query,
            answer=answer,
            citations=[asdict(citation) for citation in citations],
        )
        await self._log_usage(db, chat, turn.requester, usage, tool_calls)
        await self._prune_thread(chat.id)

        logger.info(
            "메시지 처리 완료: chat_id=%s, tools=%s, citation_count=%d, "
            "input_tokens=%d, output_tokens=%d",
            chat.id,
            [call["name"] for call in tool_calls],
            len(citations),
            usage.input_tokens,
            usage.output_tokens,
        )
        logger.debug(
            "에이전트 도구 호출: chat_id=%s, tool_calls=%s", chat.id, tool_calls
        )
        return ChatTurnResult(content=answer, citations=citations)

    async def _build_graph(self, chat: Chat, requester: User) -> CompiledStateGraph:
        """
        요청별 도구 + 요약 미들웨어 + 체크포인터로 에이전트 그래프 생성

        도구는 요청 세션 대신 세션 팩토리를 받아 호출마다 짧은 세션을 연다.

        Parameters:
            chat(Chat): 대상 채팅(모델·고정 컬렉션)
            requester(User): 요청 사용자(사용량 도구 범위)

        Returns:
            CompiledStateGraph: 실행할 에이전트 그래프
        """
        tools = [
            await build_retrieval_tool(
                self._session_factory,
                self._retrieval,
                self._collection_meta_repository,
                chat.collection_name,
            ),
            build_calculator_tool(),
            build_usage_stats_tool(
                self._session_factory, self._usage_stats, requester.id
            ),
            build_arxiv_search_tool(),
        ]
        web_search_tool = build_web_search_tool()
        if web_search_tool is not None:
            tools.append(web_search_tool)

        return create_agent(
            model=self._chat_model_registry.resolve(chat.chat_model),
            tools=tools,
            system_prompt=AGENT_SYSTEM_PROMPT,
            middleware=[
                SummarizationMiddleware(
                    model=self._chat_model_registry.resolve(CHAT_SUMMARY_MODEL),
                    trigger=("tokens", CHAT_SUMMARY_TRIGGER_TOKENS),
                    keep=("messages", CHAT_SUMMARY_KEEP_MESSAGES),
                )
            ],
            checkpointer=self._checkpointer,
        )

    def _run_config(
        self,
        chat_id: str,
        requester: User,
        usage_handler: UsageMetadataCallbackHandler,
    ) -> dict:
        """
        에이전트 실행 설정(콜백·재귀 상한·스레드 id·Langfuse 메타)

        Parameters:
            chat_id(str): 채팅 id(= thread_id)
            requester(User): 요청 사용자
            usage_handler(UsageMetadataCallbackHandler): 요약 호출 포함 토큰 집계기

        Returns:
            dict: RunnableConfig
        """
        callbacks = [self._langfuse_handler] if self._langfuse_handler else []
        return {
            "callbacks": [*callbacks, usage_handler],
            "recursion_limit": AGENT_RECURSION_LIMIT,
            "configurable": {"thread_id": chat_id},
            "metadata": {
                "langfuse_session_id": chat_id,
                "langfuse_user_id": str(requester.id),
            },
        }

    async def _rollback_thread(
        self, graph: CompiledStateGraph, run_config: dict, before: list[AnyMessage]
    ) -> None:
        """
        실패한 턴의 메시지를 스레드에서 제거(턴 시작 전 메시지로 복원)

        durability="exit"여도 실패 시 마지막 스텝 상태(답 없는 tool_calls 포함)가
        저장되므로, 그대로 두면 다음 턴이 provider에서 거부된다(CR-012 F1).
        복원 실패는 기록만 하고 원래 예외를 우선한다.

        Parameters:
            graph(CompiledStateGraph): 실행한 에이전트 그래프
            run_config(dict): 실행 설정(thread_id 포함)
            before(list[AnyMessage]): 턴 시작 전 스레드 메시지
        """
        try:
            await graph.aupdate_state(
                run_config,
                {"messages": [RemoveMessage(id=REMOVE_ALL_MESSAGES), *before]},
            )
        except Exception:
            logger.exception(
                "스레드 롤백 실패: chat_id=%s", run_config["configurable"]["thread_id"]
            )

    async def _log_usage(
        self,
        db: AsyncSession,
        chat: Chat,
        requester: User,
        usage: TurnUsage,
        tool_calls: list[dict],
    ) -> None:
        """
        턴 토큰 사용량·도구 호출 이력 기록

        Parameters:
            db(AsyncSession): DB 세션
            chat(Chat): 대상 채팅
            requester(User): 요청 사용자
            usage(TurnUsage): 이번 턴 토큰 합계(요약 호출 포함)
            tool_calls(list[dict]): 이번 턴 도구 호출(이름+인자)
        """
        await self._log_repository.create_chat_usage_log(
            db,
            model=chat.chat_model,
            input_tokens=usage.input_tokens,
            output_tokens=usage.output_tokens,
            reasoning_tokens=usage.reasoning_tokens,
            requester_id=requester.id,
            requester_email=requester.email,
            collection_name=chat.collection_name,
            conversation_id=chat.id,
        )
        await self._log_repository.create_agent_tool_call_logs(
            db,
            tool_calls=tool_calls,
            conversation_id=chat.id,
            requester_id=requester.id,
            requester_email=requester.email,
        )

    async def _prune_thread(self, chat_id: str) -> None:
        """
        성공한 턴 이후 오래된 체크포인트 정리(최신 1개만 유지, best-effort)

        Parameters:
            chat_id(str): 채팅 id(= thread_id)
        """
        try:
            await self._checkpointer.aprune([chat_id], strategy="keep_latest")
        except Exception:
            logger.warning("체크포인트 정리 실패: chat_id=%s", chat_id, exc_info=True)


def _truncate_title(title: str | None) -> str | None:
    """
    채팅 제목 말줄임(상한 초과 시 상한 글자 + "…")

    Parameters:
        title(str | None): 공백 정규화된 첫 사용자 질문 미리보기

    Returns:
        str | None: 표시용 제목(메시지 없으면 None)
    """
    if title is None or len(title) <= CHAT_TITLE_MAX_LENGTH:
        return title
    return title[:CHAT_TITLE_MAX_LENGTH] + CHAT_TITLE_ELLIPSIS


async def _shielded(coroutine: Coroutine[Any, Any, Any]) -> None:
    """
    취소되지 않도록 보호한 채 코루틴을 끝까지 실행

    asyncio task.cancel()(edge: 한 번)은 asyncio.shield가, Starlette의 anyio cancel
    scope 취소(level: 이후 await마다 재발생)는 shield된 CancelScope가 막는다.
    내부 작업이 끝난 뒤 취소를 전파한다(롤백·잠금 해제가 중간에 끊기는 것을 방지).

    Parameters:
        coroutine(Coroutine[Any, Any, Any]): 보호할 코루틴(반환값은 버림)
    """
    task = asyncio.ensure_future(coroutine)
    with anyio.CancelScope(shield=True):
        try:
            await asyncio.shield(task)
        except asyncio.CancelledError:
            await task
            raise


async def _next_before(
    stream: AsyncGenerator[Any, None], deadline: float
) -> Any | None:
    """
    턴 마감 시각 안에 그래프 스트림의 다음 항목 수신(끝나면 None, 넘으면 TimeoutError)

    Parameters:
        stream(AsyncGenerator[Any, None]): 그래프 astream 제너레이터
        deadline(float): 이벤트 루프 시계 기준 턴 마감 시각

    Returns:
        Any | None: (message chunk, metadata) 또는 스트림 종료 시 None
    """
    async with asyncio.timeout_at(deadline):
        return await anext(stream, None)


def _answer_token(chunk: AnyMessage, metadata: dict) -> str:
    """
    스트림 chunk 중 에이전트 모델 노드의 답변 텍스트만 반환

    요약 미들웨어 노드 출력·도구 노드 메시지는 제외하고, 텍스트가 없는
    tool_call 조각은 빈 문자열이 된다.

    Parameters:
        chunk(AnyMessage): 메시지 chunk
        metadata(dict): LangGraph 스트림 메타데이터(langgraph_node 포함)

    Returns:
        str: 보낼 답변 조각(보낼 것이 없으면 빈 문자열)
    """
    if metadata.get("langgraph_node") != CHAT_STREAM_MODEL_NODE:
        return ""
    return chunk.text


def _new_messages(
    messages: list[AnyMessage], before: list[AnyMessage]
) -> list[AnyMessage]:
    """
    실행 후 스레드 메시지 중 이번 턴에 새로 생긴 메시지만 반환

    턴 시작 전 메시지 id로 거른다. 턴 도중 요약으로 이번 질문(HumanMessage)이
    잘려도 이번 턴의 도구 결과·답변은 남는다(CR-012 F4).

    Parameters:
        messages(list[AnyMessage]): 실행 후 스레드 메시지
        before(list[AnyMessage]): 턴 시작 전 스레드 메시지

    Returns:
        list[AnyMessage]: 이번 턴 메시지
    """
    before_ids = {message.id for message in before}
    return [message for message in messages if message.id not in before_ids]


def _final_answer(messages: list[AnyMessage]) -> str:
    """
    이번 턴 마지막 AIMessage 본문(최종 답변) 반환

    Parameters:
        messages(list[AnyMessage]): 이번 턴 메시지

    Returns:
        str: 최종 답변(없으면 빈 문자열)
    """
    answer = ""
    for message in messages:
        if isinstance(message, AIMessage) and message.content:
            answer = message.content
    return answer


def _tool_calls(messages: list[AnyMessage]) -> list[dict]:
    """
    이번 턴 도구 호출 목록(이름+인자) 반환

    Parameters:
        messages(list[AnyMessage]): 이번 턴 메시지

    Returns:
        list[dict]: [{"name": ..., "args": ...}]
    """
    return [
        {"name": call["name"], "args": call["args"]}
        for message in messages
        if isinstance(message, AIMessage)
        for call in message.tool_calls
    ]


def _sum_usage(usage_handler: UsageMetadataCallbackHandler) -> TurnUsage:
    """
    usage 콜백이 모은 모델별 토큰을 턴 합계로 변환(요약 모델 호출 포함)

    ponytail: 요약 모델 토큰도 채팅 모델 행에 합산(모델별 행 분리는 단가 매칭이
    필요할 때). provider 모델명(날짜 접미사)이 등록명과 달라 분리하지 않는다.

    Parameters:
        usage_handler(UsageMetadataCallbackHandler): 실행 콜백

    Returns:
        TurnUsage: 입력/출력/추론 토큰 합계
    """
    usage = TurnUsage()
    for metadata in usage_handler.usage_metadata.values():
        usage.input_tokens += metadata.get("input_tokens", 0) or 0
        usage.output_tokens += metadata.get("output_tokens", 0) or 0
        details = metadata.get("output_token_details") or {}
        usage.reasoning_tokens += details.get("reasoning", 0) or 0
    return usage


def _extract_citations(messages: list[AnyMessage]) -> list[Citation]:
    """
    도구(ToolMessage)의 JSON 결과를 파싱해 인용 목록으로 변환

    문서 검색 도구, 웹 검색 도구, arXiv 검색 도구 결과를 모두 인용으로 취급하며, 같은
    출처(chunk_id 또는 url)가 여러 번 검색돼도 한 번만 남긴다.

    Parameters:
        messages(list[AnyMessage]): 이번 턴 메시지

    Returns:
        list[Citation]: 중복 제거된 인용 목록
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
        elif message.name in (WEB_SEARCH_TOOL_NAME, ARXIV_SEARCH_TOOL_NAME):
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
