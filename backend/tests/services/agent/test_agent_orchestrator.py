import asyncio
import json
import logging
from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from langchain.agents.middleware import SummarizationMiddleware
from langchain_core.callbacks import UsageMetadataCallbackHandler
from langchain_core.language_models.fake_chat_models import GenericFakeChatModel
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
from langgraph.checkpoint.memory import InMemorySaver

from core.constants import CHAT_SUMMARY_MODEL
from exceptions.chat import (
    ChatAccessDeniedError,
    ChatNotFoundError,
    ChatTurnInProgressError,
    UnsupportedChatModelError,
)
from exceptions.document import CollectionMetaNotFoundError
from models import Chat, ChatMessage, User
from schemes.dto.chat import ChatSummary
from services.agent.agent_orchestrator import AgentChatOrchestrator, _extract_citations


class _SessionFactory:
    """호출마다 새 AsyncMock 세션을 내주는 async_sessionmaker 대역."""

    def __call__(self) -> "_SessionFactory":
        return self

    async def __aenter__(self) -> AsyncMock:
        return AsyncMock()

    async def __aexit__(self, *exc_info) -> None:
        return None


def _redis(acquired: bool = True) -> AsyncMock:
    redis_client = AsyncMock()
    redis_client.set_if_absent.return_value = acquired
    return redis_client


def _make_orchestrator(**overrides):
    checkpointer = MagicMock()
    checkpointer.aprune = AsyncMock()
    checkpointer.adelete_thread = AsyncMock()
    deps = dict(
        chat_repository=AsyncMock(),
        chat_model_registry=MagicMock(),
        collection_meta_repository=AsyncMock(),
        retrieval_service=AsyncMock(),
        usage_stats_service=AsyncMock(),
        log_repository=AsyncMock(),
        langfuse_handler=None,
        checkpointer=checkpointer,
        redis_client=_redis(),
        session_factory=_SessionFactory(),
    )
    deps.update(overrides)
    return AgentChatOrchestrator(**deps), deps


def _chat(owner_id: int | None = 1, collection_name: str | None = "docs") -> Chat:
    return Chat(
        id="c1",
        collection_name=collection_name,
        chat_model="gpt-4o-mini",
        owner_id=owner_id,
    )


def _user(user_id: int = 1) -> User:
    return User(id=user_id, google_sub="sub", email="a@b.com")


def _usage(input_tokens: int, output_tokens: int, reasoning: int = 0) -> dict:
    return {
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "total_tokens": input_tokens + output_tokens,
        "output_token_details": {"reasoning": reasoning},
    }


def _fake_graph(
    messages: list, usage: dict | None = None, before: list | None = None
) -> MagicMock:
    """
    체크포인터 그래프 대역

    ainvoke는 messages를 최종 상태로 돌려주고, 실행 콜백의
    UsageMetadataCallbackHandler에 모델별 usage(요약 호출 포함)를 채운다.
    aget_state는 턴 시작 전 스레드 메시지(before)를 돌려준다.
    """

    async def ainvoke(state, config, **kwargs):
        for callback in config["callbacks"]:
            if isinstance(callback, UsageMetadataCallbackHandler):
                callback.usage_metadata = dict(usage or {})
        return {"messages": messages}

    graph = MagicMock()
    graph.ainvoke = AsyncMock(side_effect=ainvoke)
    graph.aget_state = AsyncMock(
        return_value=SimpleNamespace(values={"messages": list(before or [])})
    )
    graph.aupdate_state = AsyncMock()
    return graph


def _tool_message(**kwargs) -> ToolMessage:
    defaults = dict(content="{}", name="search_documents", tool_call_id="t1")
    defaults.update(kwargs)
    return ToolMessage(**defaults)


def _send(orchestrator, db=None, chat_id: str = "c1", query: str = "질문"):
    return asyncio.run(
        orchestrator.send_message(
            db or AsyncMock(), chat_id=chat_id, query=query, requester=_user()
        )
    )


def test_create_chat_success():
    # 모델·컬렉션 매핑이 모두 유효하면 채팅을 생성한다.
    orchestrator, deps = _make_orchestrator()
    deps[
        "collection_meta_repository"
    ].get_collection_metadata.return_value = MagicMock()
    expected_chat = _chat()
    deps["chat_repository"].create_chat.return_value = expected_chat

    result = asyncio.run(
        orchestrator.create_chat(
            AsyncMock(), collection_name="docs", chat_model="gpt-4o-mini", owner_id=1
        )
    )

    assert result is expected_chat
    deps["chat_model_registry"].get_info.assert_called_once_with("gpt-4o-mini")


def test_create_chat_success_with_no_collection():
    # collection_name 미지정이면 컬렉션 매핑 검증을 생략한다(에이전트가 매 질의마다 선택).
    orchestrator, deps = _make_orchestrator()
    expected_chat = _chat(collection_name=None)
    deps["chat_repository"].create_chat.return_value = expected_chat

    result = asyncio.run(
        orchestrator.create_chat(
            AsyncMock(), collection_name=None, chat_model="gpt-4o-mini", owner_id=1
        )
    )

    assert result is expected_chat
    deps["collection_meta_repository"].get_collection_metadata.assert_not_awaited()


def test_create_chat_failed_with_unsupported_model():
    # 미등록 채팅 모델이면 컬렉션 조회 없이 즉시 예외를 던진다.
    orchestrator, deps = _make_orchestrator()
    deps["chat_model_registry"].get_info.side_effect = UnsupportedChatModelError(
        message="chat model 'bad' is not registered", code_path="p"
    )

    with pytest.raises(UnsupportedChatModelError):
        asyncio.run(
            orchestrator.create_chat(
                AsyncMock(), collection_name="docs", chat_model="bad", owner_id=1
            )
        )

    deps["collection_meta_repository"].get_collection_metadata.assert_not_awaited()


def test_create_chat_failed_with_missing_collection_meta():
    # 컬렉션이 지정됐는데 임베딩 모델 매핑이 없으면 CollectionMetaNotFoundError
    orchestrator, deps = _make_orchestrator()
    deps["collection_meta_repository"].get_collection_metadata.return_value = None

    with pytest.raises(CollectionMetaNotFoundError):
        asyncio.run(
            orchestrator.create_chat(
                AsyncMock(),
                collection_name="missing",
                chat_model="gpt-4o-mini",
                owner_id=1,
            )
        )

    deps["chat_repository"].create_chat.assert_not_awaited()


def test_send_message_success_with_call_order():
    """
    메시지 전송(성공) - 인용 추출, usage 콜백 합산, 턴 단위 메시지 저장

    입력 데이터
        - 검색 도구 결과 1건 + 최종 답변 "답변"
        - usage 콜백: 채팅 모델 7+10 입력, 요약 모델 100 입력(모델별 집계)

    예상 출력 데이터
        - 답변 "답변", 인용 1건
        - 사용자+답변 메시지를 add_turn_messages 한 번으로 저장
        - 사용량 로그에 요약 토큰까지 합산(input 117, output 5+20, reasoning 2)
    """
    orchestrator, deps = _make_orchestrator()
    deps["chat_repository"].get_chat.return_value = _chat()
    messages = [
        HumanMessage(content="질문"),
        AIMessage(content=""),
        _tool_message(
            content=json.dumps(
                {
                    "results": [
                        {
                            "chunk_id": "c1",
                            "document_id": "d1",
                            "filename": "a.txt",
                            "collection_name": "docs",
                            "snippet": "본문",
                        }
                    ]
                }
            )
        ),
        AIMessage(content="답변"),
    ]
    usage = {
        "gpt-4o-2024-08-06": _usage(17, 5, reasoning=2),
        "gpt-4o-mini-2024-07-18": _usage(100, 20),
    }

    with patch(
        "services.agent.agent_orchestrator.create_agent",
        return_value=_fake_graph(messages, usage),
    ):
        result = _send(orchestrator)

    assert result.content == "답변"
    assert len(result.citations) == 1
    assert result.citations[0].chunk_id == "c1"
    deps["chat_repository"].add_turn_messages.assert_awaited_once()
    _, kwargs = deps["chat_repository"].add_turn_messages.call_args
    assert kwargs["chat_id"] == "c1"
    assert kwargs["query"] == "질문"
    assert kwargs["answer"] == "답변"
    assert kwargs["citations"][0]["chunk_id"] == "c1"
    _, kwargs = deps["log_repository"].create_chat_usage_log.call_args
    assert kwargs["conversation_id"] == "c1"
    assert kwargs["input_tokens"] == 117
    assert kwargs["output_tokens"] == 25
    assert kwargs["reasoning_tokens"] == 2


def test_send_message_success_with_tool_calls_saved_to_log():
    """
    메시지 전송(성공) - 도구 호출 이력 저장, INFO 로그에는 인자·이메일 미포함

    입력 데이터
        - search_documents(query="비밀 질의") 호출 1회

    예상 출력 데이터
        - agent_tool_call_logs에 이름+인자 저장
        - INFO 로그에 도구 인자와 요청자 이메일이 없음(id만)
    """
    orchestrator, deps = _make_orchestrator()
    deps["chat_repository"].get_chat.return_value = _chat()
    messages = [
        HumanMessage(content="질문"),
        AIMessage(
            content="",
            tool_calls=[
                {
                    "name": "search_documents",
                    "args": {"query": "비밀 질의", "collection_name": "docs"},
                    "id": "call_1",
                    "type": "tool_call",
                }
            ],
        ),
        _tool_message(content=json.dumps({"results": []}), tool_call_id="call_1"),
        AIMessage(content="답변"),
    ]
    logger = logging.getLogger("services.agent.agent_orchestrator")
    records: list[logging.LogRecord] = []
    handler = logging.Handler()
    handler.emit = records.append
    logger.addHandler(handler)
    previous_level = logger.level
    logger.setLevel(logging.INFO)

    try:
        with patch(
            "services.agent.agent_orchestrator.create_agent",
            return_value=_fake_graph(messages),
        ):
            _send(orchestrator)
    finally:
        logger.removeHandler(handler)
        logger.setLevel(previous_level)

    _, kwargs = deps["log_repository"].create_agent_tool_call_logs.call_args
    assert kwargs["tool_calls"] == [
        {
            "name": "search_documents",
            "args": {"query": "비밀 질의", "collection_name": "docs"},
        }
    ]
    info_text = " ".join(
        record.getMessage() for record in records if record.levelno >= logging.INFO
    )
    assert "비밀 질의" not in info_text
    assert "a@b.com" not in info_text
    assert "search_documents" in info_text


def test_send_message_success_with_langfuse_handler_included():
    """
    메시지 전송(성공) - Langfuse 핸들러와 usage 핸들러가 실행 콜백에 포함

    입력 데이터
        - langfuse_handler 설정됨

    예상 출력 데이터
        - callbacks에 langfuse 핸들러 + UsageMetadataCallbackHandler
        - metadata에 세션/유저 id
    """
    handler = MagicMock()
    orchestrator, deps = _make_orchestrator(langfuse_handler=handler)
    deps["chat_repository"].get_chat.return_value = _chat()
    graph = _fake_graph([AIMessage(content="답변")])

    with patch("services.agent.agent_orchestrator.create_agent", return_value=graph):
        _send(orchestrator)

    config = graph.ainvoke.call_args.kwargs["config"]
    assert config["callbacks"][0] is handler
    assert isinstance(config["callbacks"][1], UsageMetadataCallbackHandler)
    assert config["metadata"]["langfuse_session_id"] == "c1"
    assert config["metadata"]["langfuse_user_id"] == "1"


def test_send_message_failed_with_missing_chat():
    """
    메시지 전송(실패) - 존재하지 않는 채팅

    입력 데이터
        - chat_id = "missing"(조회 결과 None)

    예상 출력 데이터
        - raise ChatNotFoundError(404), 잠금 시도 없음
    """
    orchestrator, deps = _make_orchestrator()
    deps["chat_repository"].get_chat.return_value = None

    with pytest.raises(ChatNotFoundError) as exc_info:
        _send(orchestrator, chat_id="missing")

    assert exc_info.value.message == "Chat not found."

    deps["redis_client"].set_if_absent.assert_not_awaited()


def test_send_message_failed_with_other_users_chat():
    """
    메시지 전송(실패) - 다른 사용자의 채팅(IDOR 방지)

    입력 데이터
        - 채팅 owner_id = 99, 요청자 id = 1

    예상 출력 데이터
        - raise ChatAccessDeniedError(403)
    """
    orchestrator, deps = _make_orchestrator()
    deps["chat_repository"].get_chat.return_value = _chat(owner_id=99)

    with pytest.raises(ChatAccessDeniedError) as exc_info:
        _send(orchestrator)

    # 클라이언트에 노출되는 메시지에 user id·chat id가 없어야 한다(KI-058).
    assert exc_info.value.message == "You do not have access to this chat."


def test_send_message_failed_with_turn_in_progress():
    """
    메시지 전송(실패) - 같은 채팅의 이전 턴이 진행 중(동시 전송)

    입력 데이터
        - Redis SET NX 실패(이미 잠금 존재)

    예상 출력 데이터
        - raise ChatTurnInProgressError(409)
        - 에이전트 실행·메시지 저장 없음, 남의 잠금을 해제하지 않음
    """
    orchestrator, deps = _make_orchestrator(redis_client=_redis(acquired=False))
    deps["chat_repository"].get_chat.return_value = _chat()

    with patch("services.agent.agent_orchestrator.create_agent") as create_agent:
        with pytest.raises(ChatTurnInProgressError) as exc_info:
            _send(orchestrator)

    assert "c1" not in exc_info.value.message
    assert exc_info.value.message.isascii()

    create_agent.assert_not_called()
    deps["chat_repository"].add_turn_messages.assert_not_awaited()
    deps["redis_client"].delete.assert_not_awaited()


def test_send_message_failed_with_chat_deleted_after_lock():
    """
    메시지 전송(실패) - 잠금 대기 중 채팅이 삭제됨(전송·삭제 경합)

    입력 데이터
        - get_chat: 잠금 전 = 채팅, 잠금 후 재확인 = None

    예상 출력 데이터
        - raise ChatNotFoundError(404), 에이전트 미실행, 잠금 해제
    """
    orchestrator, deps = _make_orchestrator()
    deps["chat_repository"].get_chat.side_effect = [_chat(), None]

    with patch("services.agent.agent_orchestrator.create_agent") as create_agent:
        with pytest.raises(ChatNotFoundError):
            _send(orchestrator)

    create_agent.assert_not_called()
    deps["chat_repository"].add_turn_messages.assert_not_awaited()
    deps["redis_client"].delete.assert_awaited_once_with("chat:turn-lock:c1")


def test_send_message_success_with_lock_acquired_and_released():
    """
    메시지 전송(성공) - 채팅별 잠금을 TTL과 함께 잡고 끝나면 해제

    입력 데이터
        - chat_id = "c1", 정상 턴

    예상 출력 데이터
        - set_if_absent("chat:turn-lock:c1", ex=TTL>턴 상한) 후 delete 같은 키
    """
    from core.constants import CHAT_TURN_LOCK_TTL_SECONDS, CHAT_TURN_TIMEOUT_SECONDS

    orchestrator, deps = _make_orchestrator()
    deps["chat_repository"].get_chat.return_value = _chat()

    with patch(
        "services.agent.agent_orchestrator.create_agent",
        return_value=_fake_graph([AIMessage(content="답변")]),
    ):
        _send(orchestrator)

    args, kwargs = deps["redis_client"].set_if_absent.call_args
    assert args[0] == "chat:turn-lock:c1"
    assert kwargs["ex"] == CHAT_TURN_LOCK_TTL_SECONDS
    assert CHAT_TURN_LOCK_TTL_SECONDS > CHAT_TURN_TIMEOUT_SECONDS
    deps["redis_client"].delete.assert_awaited_once_with("chat:turn-lock:c1")


def test_send_message_failed_with_agent_error_rolls_back_and_releases_lock():
    """
    메시지 전송(실패) - 에이전트 실패 시 스레드를 턴 시작 전 메시지로 복원

    입력 데이터
        - 턴 시작 전 스레드 메시지 [이전 질문]
        - graph.ainvoke가 RuntimeError

    예상 출력 데이터
        - RuntimeError 전파
        - aupdate_state로 RemoveMessage(전체) + 이전 메시지 재기록
        - chat_messages·사용량 저장 없음, 잠금 해제
    """
    orchestrator, deps = _make_orchestrator()
    deps["chat_repository"].get_chat.return_value = _chat()
    previous = HumanMessage(content="이전 질문", id="h0")
    graph = _fake_graph([], before=[previous])
    graph.ainvoke = AsyncMock(side_effect=RuntimeError("qdrant down"))

    with patch("services.agent.agent_orchestrator.create_agent", return_value=graph):
        with pytest.raises(RuntimeError):
            _send(orchestrator)

    config, update = graph.aupdate_state.call_args.args
    assert config["configurable"] == {"thread_id": "c1"}
    remove_all, restored = update["messages"]
    assert remove_all.type == "remove"
    assert restored is previous
    deps["chat_repository"].add_turn_messages.assert_not_awaited()
    deps["log_repository"].create_chat_usage_log.assert_not_awaited()
    deps["redis_client"].delete.assert_awaited_once_with("chat:turn-lock:c1")


def test_send_message_success_with_request_session_released_before_run():
    """
    메시지 전송(성공) - 요청 세션 트랜잭션을 에이전트 실행 전에 종료

    입력 데이터
        - 요청 DB 세션(AsyncMock)

    예상 출력 데이터
        - db.commit()이 graph.ainvoke보다 먼저 호출(LLM 루프 동안 커넥션 미점유)
        - 도구 빌더에는 요청 세션이 아닌 세션 팩토리가 전달
    """
    orchestrator, deps = _make_orchestrator()
    deps["chat_repository"].get_chat.return_value = _chat()
    calls: list[str] = []
    db = AsyncMock()
    db.commit.side_effect = lambda: calls.append("commit")
    graph = _fake_graph([AIMessage(content="답변")])
    original_ainvoke = graph.ainvoke.side_effect

    async def ainvoke(state, config, **kwargs):
        calls.append("ainvoke")
        return await original_ainvoke(state, config, **kwargs)

    graph.ainvoke.side_effect = ainvoke

    with (
        patch("services.agent.agent_orchestrator.create_agent", return_value=graph),
        patch(
            "services.agent.agent_orchestrator.build_retrieval_tool",
            new=AsyncMock(return_value=MagicMock()),
        ) as build_retrieval_tool,
    ):
        _send(orchestrator, db=db)

    assert calls.index("commit") < calls.index("ainvoke")
    assert build_retrieval_tool.call_args.args[0] is deps["session_factory"]


def test_send_message_success_with_checkpointer_thread_and_summarization():
    """
    메시지 전송(성공) - 체크포인터 스레드·요약 미들웨어·durability 설정

    입력 데이터
        - chat_id = "c1", query = "질문"

    예상 출력 데이터
        - 현재 질문만 입력, thread_id = chat_id, durability = "exit"
        - SummarizationMiddleware는 가장 싼 등록 모델(CHAT_SUMMARY_MODEL)로 요약
        - 성공 후 checkpointer.aprune(["c1"], strategy="keep_latest")
    """
    orchestrator, deps = _make_orchestrator()
    deps["chat_repository"].get_chat.return_value = _chat()
    summary_model = MagicMock()
    deps["chat_model_registry"].resolve.side_effect = lambda name: (
        summary_model if name == CHAT_SUMMARY_MODEL else MagicMock()
    )
    graph = _fake_graph([HumanMessage(content="질문"), AIMessage(content="답변")])

    with patch(
        "services.agent.agent_orchestrator.create_agent", return_value=graph
    ) as create_agent:
        _send(orchestrator)

    agent_kwargs = create_agent.call_args.kwargs
    assert agent_kwargs["checkpointer"] is deps["checkpointer"]
    (summarizer,) = [
        m for m in agent_kwargs["middleware"] if isinstance(m, SummarizationMiddleware)
    ]
    assert summarizer.model is summary_model
    (state,) = graph.ainvoke.call_args.args
    assert state["messages"][0].content == "질문"
    assert graph.ainvoke.call_args.kwargs["config"]["configurable"] == {
        "thread_id": "c1"
    }
    assert graph.ainvoke.call_args.kwargs["durability"] == "exit"
    deps["checkpointer"].aprune.assert_awaited_once_with(["c1"], strategy="keep_latest")


def test_send_message_success_with_prune_failure_ignored():
    """
    메시지 전송(성공) - 체크포인트 정리 실패는 턴 결과에 영향 없음

    입력 데이터
        - checkpointer.aprune이 NotImplementedError

    예상 출력 데이터
        - 답변 정상 반환, 메시지 저장 완료
    """
    orchestrator, deps = _make_orchestrator()
    deps["chat_repository"].get_chat.return_value = _chat()
    deps["checkpointer"].aprune.side_effect = NotImplementedError

    with patch(
        "services.agent.agent_orchestrator.create_agent",
        return_value=_fake_graph([AIMessage(content="답변")]),
    ):
        result = _send(orchestrator)

    assert result.content == "답변"
    deps["chat_repository"].add_turn_messages.assert_awaited_once()


def test_send_message_success_with_only_current_turn_counted():
    """
    메시지 전송(성공) - 이전 턴 메시지는 답변·인용 집계에서 제외

    입력 데이터
        - 턴 시작 전 스레드: [이전 질문(h0), 이전 답변(a0), 이전 도구 결과(t0)]
        - 실행 후 스레드: 이전 메시지 + [질문, 답변]

    예상 출력 데이터
        - 답변 "답변", 인용 없음(이전 도구 결과 제외)
    """
    orchestrator, deps = _make_orchestrator()
    deps["chat_repository"].get_chat.return_value = _chat()
    before = [
        HumanMessage(content="이전 질문", id="h0"),
        AIMessage(content="이전 답변", id="a0"),
        _tool_message(
            content=json.dumps({"results": [{"chunk_id": "old", "filename": "a"}]}),
            tool_call_id="old",
            id="t0",
        ),
    ]
    messages = [*before, HumanMessage(content="질문"), AIMessage(content="답변")]

    with patch(
        "services.agent.agent_orchestrator.create_agent",
        return_value=_fake_graph(messages, before=before),
    ):
        result = _send(orchestrator)

    assert result.content == "답변"
    assert result.citations == []


def test_send_message_success_with_turn_messages_kept_after_mid_turn_summary():
    """
    메시지 전송(성공) - 턴 도중 요약으로 이번 질문이 잘려도 이번 턴 결과 집계

    입력 데이터
        - 턴 시작 전 스레드: [이전 질문(h0), 이전 답변(a0)]
        - 실행 후 스레드: [요약(HumanMessage, 새 id), 도구 결과, 답변](이번 질문 소실)

    예상 출력 데이터
        - 답변 "답변", 이번 턴 도구 결과의 인용 1건 유지
    """
    orchestrator, deps = _make_orchestrator()
    deps["chat_repository"].get_chat.return_value = _chat()
    before = [
        HumanMessage(content="이전 질문", id="h0"),
        AIMessage(content="이전 답변", id="a0"),
    ]
    messages = [
        HumanMessage(content="요약: ...", id="summary"),
        _tool_message(
            content=json.dumps({"results": [{"chunk_id": "new", "filename": "b"}]}),
            id="t1",
        ),
        AIMessage(content="답변", id="a1"),
    ]

    with patch(
        "services.agent.agent_orchestrator.create_agent",
        return_value=_fake_graph(messages, before=before),
    ):
        result = _send(orchestrator)

    assert result.content == "답변"
    assert [c.chunk_id for c in result.citations] == ["new"]


class _ToolCallingFakeModel(GenericFakeChatModel):
    """bind_tools를 지원하는 스크립트형 가짜 채팅 모델(create_agent용)."""

    def bind_tools(self, tools, **kwargs):
        return self


def test_send_message_failed_with_tool_error_leaves_no_dangling_tool_calls():
    """
    메시지 전송(실패→복구) - 실제 InMemorySaver 그래프로 실패 턴 원자성 검증(CR-012 F1)

    입력 데이터
        - 1턴: 정상 답변 "첫 답변"
        - 2턴: 모델이 search_documents tool_call → 검색이 RuntimeError
        - 3턴: 정상 답변 "셋째 답변"

    예상 출력 데이터
        - 2턴 RuntimeError, 스레드는 1턴 메시지 그대로(답 없는 tool_calls 없음)
        - 3턴 성공, 스레드 = [1턴 질문, 첫 답변, 3턴 질문, 셋째 답변]
        - chat_messages 저장은 성공한 1·3턴만
    """
    checkpointer = InMemorySaver()
    retrieval_service = AsyncMock()
    retrieval_service.retrieve.side_effect = RuntimeError("qdrant down")
    model = _ToolCallingFakeModel(
        messages=iter(
            [
                AIMessage(content="첫 답변"),
                AIMessage(
                    content="",
                    tool_calls=[
                        {
                            "name": "search_documents",
                            "args": {"query": "q"},
                            "id": "call_1",
                            "type": "tool_call",
                        }
                    ],
                ),
                AIMessage(content="셋째 답변"),
            ]
        )
    )
    registry = MagicMock()
    registry.resolve.return_value = model
    orchestrator, deps = _make_orchestrator(
        checkpointer=checkpointer,
        chat_model_registry=registry,
        retrieval_service=retrieval_service,
    )
    deps["chat_repository"].get_chat.return_value = _chat()

    async def thread_messages() -> list:
        state = await checkpointer.aget_tuple({"configurable": {"thread_id": "c1"}})
        return state.checkpoint["channel_values"]["messages"]

    async def scenario() -> list:
        await orchestrator.send_message(
            AsyncMock(), chat_id="c1", query="첫 질문", requester=_user()
        )
        with pytest.raises(RuntimeError):
            await orchestrator.send_message(
                AsyncMock(), chat_id="c1", query="둘째 질문", requester=_user()
            )
        after_failure = await thread_messages()
        assert [m.content for m in after_failure] == ["첫 질문", "첫 답변"]
        await orchestrator.send_message(
            AsyncMock(), chat_id="c1", query="셋째 질문", requester=_user()
        )
        return await thread_messages()

    with patch(
        "services.agent.agent_orchestrator.build_web_search_tool", return_value=None
    ):
        final_messages = asyncio.run(scenario())

    assert [m.content for m in final_messages] == [
        "첫 질문",
        "첫 답변",
        "셋째 질문",
        "셋째 답변",
    ]
    assert not any(getattr(m, "tool_calls", None) for m in final_messages)
    saved_answers = [
        call.kwargs["answer"]
        for call in deps["chat_repository"].add_turn_messages.await_args_list
    ]
    assert saved_answers == ["첫 답변", "셋째 답변"]


def test_get_messages_success_with_owner():
    """
    채팅 이력 조회(성공) - 소유자

    입력 데이터
        - chat_id = "c1", 요청자 = 소유자, 저장된 메시지 2건

    예상 출력 데이터
        - chat_model/collection_name + 메시지 2건(저장소 정렬 순서 그대로)
    """
    orchestrator, deps = _make_orchestrator()
    deps["chat_repository"].get_chat.return_value = _chat()
    rows = [
        ChatMessage(chat_id="c1", role="user", content="질문", citations=None),
        ChatMessage(chat_id="c1", role="assistant", content="답변", citations=[]),
    ]
    deps["chat_repository"].list_messages.return_value = rows

    history = asyncio.run(
        orchestrator.get_messages(AsyncMock(), chat_id="c1", requester=_user())
    )

    assert history.chat_model == "gpt-4o-mini"
    assert history.collection_name == "docs"
    assert history.messages == rows


def test_get_messages_failed_with_missing_chat():
    """
    채팅 이력 조회(실패) - 존재하지 않는 채팅

    입력 데이터
        - chat_id = "missing"

    예상 출력 데이터
        - raise ChatNotFoundError(404), 메시지 조회 없음
    """
    orchestrator, deps = _make_orchestrator()
    deps["chat_repository"].get_chat.return_value = None

    with pytest.raises(ChatNotFoundError):
        asyncio.run(
            orchestrator.get_messages(AsyncMock(), chat_id="missing", requester=_user())
        )

    deps["chat_repository"].list_messages.assert_not_awaited()


def test_get_messages_failed_with_other_users_chat():
    """
    채팅 이력 조회(실패) - 다른 사용자의 채팅

    입력 데이터
        - 채팅 owner_id = 99, 요청자 id = 1

    예상 출력 데이터
        - raise ChatAccessDeniedError(403), 메시지 조회 없음
    """
    orchestrator, deps = _make_orchestrator()
    deps["chat_repository"].get_chat.return_value = _chat(owner_id=99)

    with pytest.raises(ChatAccessDeniedError):
        asyncio.run(
            orchestrator.get_messages(AsyncMock(), chat_id="c1", requester=_user())
        )

    deps["chat_repository"].list_messages.assert_not_awaited()


def test_extract_citations_success_with_document_and_web_sources():
    # 문서 검색과 웹 검색 도구 결과를 모두 인용으로 변환하고, 중복은 한 번만 남긴다.
    messages = [
        _tool_message(
            name="search_documents",
            content=json.dumps(
                {
                    "results": [
                        {
                            "chunk_id": "c1",
                            "document_id": "d1",
                            "filename": "a.txt",
                            "collection_name": "docs",
                            "snippet": "본문",
                        },
                        {
                            "chunk_id": "c1",  # 중복, 한 번만 남아야 함
                            "document_id": "d1",
                            "filename": "a.txt",
                            "collection_name": "docs",
                            "snippet": "본문",
                        },
                    ]
                }
            ),
        ),
        _tool_message(
            name="tavily_search",
            content=json.dumps(
                {
                    "results": [
                        {
                            "title": "뉴스 제목",
                            "url": "https://example.com",
                            "content": "웹 검색 내용",
                        }
                    ]
                }
            ),
        ),
        _tool_message(
            name="arxiv_search",
            content=json.dumps(
                {
                    "results": [
                        {
                            "title": "A Great Paper",
                            "url": "http://arxiv.org/abs/1234.5678v1",
                            "content": "초록 내용",
                        }
                    ]
                }
            ),
        ),
    ]

    citations = _extract_citations(messages)

    assert len(citations) == 3
    doc_citation = next(c for c in citations if c.source_type == "document")
    web_citation = next(c for c in citations if c.url == "https://example.com")
    arxiv_citation = next(
        c for c in citations if c.url == "http://arxiv.org/abs/1234.5678v1"
    )
    assert doc_citation.chunk_id == "c1"
    assert web_citation.title == "뉴스 제목"
    assert arxiv_citation.source_type == "web"
    assert arxiv_citation.title == "A Great Paper"


def test_send_message_failed_with_cancel_mid_tool_call_rolls_back():
    """
    메시지 전송(실패) - 도구 실행 중 취소(배포 SIGTERM, 클라이언트 끊김) 시에도 롤백(CR-014 F1)

    입력 데이터
        - 실제 InMemorySaver 그래프, 모델이 search_documents tool_call
        - 검색 도구 실행 중 요청 task를 cancel

    예상 출력 데이터
        - CancelledError 전파
        - 스레드에 답 없는 tool_calls가 남지 않음(턴 시작 전 상태 = 빈 스레드)
        - Redis 잠금 해제, chat_messages 저장 없음
    """
    checkpointer = InMemorySaver()
    tool_started = asyncio.Event()

    async def hang(*args, **kwargs):
        tool_started.set()
        await asyncio.Event().wait()

    retrieval_service = AsyncMock()
    retrieval_service.retrieve.side_effect = hang
    model = _ToolCallingFakeModel(
        messages=iter(
            [
                AIMessage(
                    content="",
                    tool_calls=[
                        {
                            "name": "search_documents",
                            "args": {"query": "q"},
                            "id": "call_1",
                            "type": "tool_call",
                        }
                    ],
                )
            ]
        )
    )
    registry = MagicMock()
    registry.resolve.return_value = model
    orchestrator, deps = _make_orchestrator(
        checkpointer=checkpointer,
        chat_model_registry=registry,
        retrieval_service=retrieval_service,
    )
    deps["chat_repository"].get_chat.return_value = _chat()

    async def scenario() -> list:
        task = asyncio.create_task(
            orchestrator.send_message(
                AsyncMock(), chat_id="c1", query="질문", requester=_user()
            )
        )
        await tool_started.wait()
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
        state = await checkpointer.aget_tuple({"configurable": {"thread_id": "c1"}})
        return state.checkpoint["channel_values"].get("messages", []) if state else []

    with patch(
        "services.agent.agent_orchestrator.build_web_search_tool", return_value=None
    ):
        messages = asyncio.run(scenario())

    assert not any(getattr(m, "tool_calls", None) for m in messages)
    assert messages == []
    deps["redis_client"].delete.assert_awaited_once_with("chat:turn-lock:c1")
    deps["chat_repository"].add_turn_messages.assert_not_awaited()


def _summary(chat_id: str, title: str | None) -> ChatSummary:
    return ChatSummary(
        id=chat_id,
        title=title,
        chat_model="gpt-4o-mini",
        collection_name=None,
        created_at=datetime(2026, 11, 26, 12, 0, tzinfo=UTC),
        last_message_at=None,
    )


def test_list_chats_success_with_owner_and_limit():
    """
    채팅 목록 조회(성공) - 요청자 소유 채팅만, 상한 100개

    입력 데이터
        - requester.id = 1, 저장소가 짧은 제목 1건 반환

    예상 출력 데이터
        - 저장소 호출 owner_id=1, limit=100, 제목은 그대로
    """
    orchestrator, deps = _make_orchestrator()
    deps["chat_repository"].list_chats.return_value = [_summary("c1", "짧은 질문")]

    chats = asyncio.run(orchestrator.list_chats(AsyncMock(), requester=_user()))

    assert [chat.title for chat in chats] == ["짧은 질문"]
    kwargs = deps["chat_repository"].list_chats.call_args.kwargs
    assert (kwargs["owner_id"], kwargs["limit"]) == (1, 100)


def test_list_chats_success_with_long_title_truncated():
    """
    채팅 목록 조회(성공) - 60자 초과 제목은 60자 + "…"

    입력 데이터
        - 저장소 미리보기: 61자("가" * 61), 정확히 60자("나" * 60)

    예상 출력 데이터
        - "가" * 60 + "…", "나" * 60(그대로)
    """
    orchestrator, deps = _make_orchestrator()
    deps["chat_repository"].list_chats.return_value = [
        _summary("c1", "가" * 61),
        _summary("c2", "나" * 60),
    ]

    chats = asyncio.run(orchestrator.list_chats(AsyncMock(), requester=_user()))

    assert [chat.title for chat in chats] == ["가" * 60 + "…", "나" * 60]


def test_list_chats_success_with_chat_without_messages():
    """
    채팅 목록 조회(성공) - 메시지 없는 채팅은 제목 null

    입력 데이터
        - 저장소 미리보기 None

    예상 출력 데이터
        - title = None
    """
    orchestrator, deps = _make_orchestrator()
    deps["chat_repository"].list_chats.return_value = [_summary("c1", None)]

    chats = asyncio.run(orchestrator.list_chats(AsyncMock(), requester=_user()))

    assert chats[0].title is None


def _delete(orchestrator, chat_id: str = "c1", user_id: int = 1) -> None:
    asyncio.run(
        orchestrator.delete_chat(AsyncMock(), chat_id=chat_id, requester=_user(user_id))
    )


def test_delete_chat_success_with_thread_and_row_deleted():
    """
    채팅 삭제(성공) - 턴 잠금을 잡고 체크포인트 스레드 + chats 행 삭제 후 잠금 해제

    입력 데이터
        - chat_id = "c1", 소유자 요청

    예상 출력 데이터
        - adelete_thread("c1"), delete_chat("c1"), 잠금 키 chat:turn-lock:c1 획득·해제
    """
    orchestrator, deps = _make_orchestrator()
    deps["chat_repository"].get_chat.return_value = _chat()

    _delete(orchestrator)

    deps["checkpointer"].adelete_thread.assert_awaited_once_with("c1")
    assert deps["chat_repository"].delete_chat.call_args.args[1] == "c1"
    assert deps["redis_client"].set_if_absent.call_args.args[0] == "chat:turn-lock:c1"
    deps["redis_client"].delete.assert_awaited_once_with("chat:turn-lock:c1")


def test_delete_chat_failed_with_turn_in_progress():
    """
    채팅 삭제(실패) - 같은 채팅 턴 진행 중(잠금 보유)

    입력 데이터
        - set_if_absent = False

    예상 출력 데이터
        - ChatTurnInProgressError(409), 아무것도 삭제하지 않고 남의 잠금도 해제하지 않음
    """
    orchestrator, deps = _make_orchestrator(redis_client=_redis(acquired=False))
    deps["chat_repository"].get_chat.return_value = _chat()

    with pytest.raises(ChatTurnInProgressError):
        _delete(orchestrator)

    deps["checkpointer"].adelete_thread.assert_not_awaited()
    deps["chat_repository"].delete_chat.assert_not_awaited()
    deps["redis_client"].delete.assert_not_awaited()


def test_delete_chat_failed_with_other_users_chat():
    """
    채팅 삭제(실패) - 다른 사용자의 채팅

    입력 데이터
        - 채팅 owner_id = 2, 요청자 id = 1

    예상 출력 데이터
        - ChatAccessDeniedError(403), 잠금·삭제 없음
    """
    orchestrator, deps = _make_orchestrator()
    deps["chat_repository"].get_chat.return_value = _chat(owner_id=2)

    with pytest.raises(ChatAccessDeniedError):
        _delete(orchestrator)

    deps["redis_client"].set_if_absent.assert_not_awaited()
    deps["chat_repository"].delete_chat.assert_not_awaited()


def test_delete_chat_failed_with_already_deleted_chat():
    """
    채팅 삭제(실패) - 이미 삭제된(없는) 채팅 재요청

    입력 데이터
        - get_chat = None (두 번째 삭제 요청)

    예상 출력 데이터
        - ChatNotFoundError(404), 추가 삭제 없음
    """
    orchestrator, deps = _make_orchestrator()
    deps["chat_repository"].get_chat.return_value = None

    with pytest.raises(ChatNotFoundError):
        _delete(orchestrator)

    deps["checkpointer"].adelete_thread.assert_not_awaited()
    deps["chat_repository"].delete_chat.assert_not_awaited()


def test_delete_chat_failed_with_checkpointer_error():
    """
    채팅 삭제(실패) - 체크포인트 삭제 실패 시 chats 행은 남기고 잠금 해제(재시도 가능)

    입력 데이터
        - adelete_thread가 RuntimeError

    예상 출력 데이터
        - RuntimeError 전파, delete_chat 미호출, 잠금 해제
    """
    orchestrator, deps = _make_orchestrator()
    deps["chat_repository"].get_chat.return_value = _chat()
    deps["checkpointer"].adelete_thread.side_effect = RuntimeError("pg down")

    with pytest.raises(RuntimeError):
        _delete(orchestrator)

    deps["chat_repository"].delete_chat.assert_not_awaited()
    deps["redis_client"].delete.assert_awaited_once_with("chat:turn-lock:c1")


def test_delete_chat_failed_with_chat_deleted_after_lock():
    """
    채팅 삭제(실패) - 잠금 대기 중 다른 요청이 먼저 삭제함(중복 삭제 경합)

    입력 데이터
        - get_chat: 잠금 전 = 채팅, 잠금 후 재확인 = None

    예상 출력 데이터
        - ChatNotFoundError(404), 스레드·행 삭제 없음, 잠금 해제
    """
    orchestrator, deps = _make_orchestrator()
    deps["chat_repository"].get_chat.side_effect = [_chat(), None]

    with pytest.raises(ChatNotFoundError):
        _delete(orchestrator)

    deps["checkpointer"].adelete_thread.assert_not_awaited()
    deps["chat_repository"].delete_chat.assert_not_awaited()
    deps["redis_client"].delete.assert_awaited_once_with("chat:turn-lock:c1")


def test_delete_chat_success_with_read_transaction_ended_before_lock():
    """
    채팅 삭제(성공) - 소유권 조회 트랜잭션을 잠금·스레드 삭제 전에 종료

    입력 데이터
        - 요청 DB 세션(AsyncMock)

    예상 출력 데이터
        - db.commit()이 잠금 획득과 adelete_thread보다 먼저 호출
    """
    orchestrator, deps = _make_orchestrator()
    deps["chat_repository"].get_chat.return_value = _chat()
    calls: list[str] = []
    db = AsyncMock()
    db.commit.side_effect = lambda: calls.append("commit")
    deps["redis_client"].set_if_absent.side_effect = lambda *a, **k: (
        calls.append("lock") or True
    )
    deps["checkpointer"].adelete_thread.side_effect = lambda *a: calls.append(
        "adelete_thread"
    )

    asyncio.run(orchestrator.delete_chat(db, chat_id="c1", requester=_user()))

    assert calls[0] == "commit"
    assert calls.index("commit", 1) < calls.index("adelete_thread")
