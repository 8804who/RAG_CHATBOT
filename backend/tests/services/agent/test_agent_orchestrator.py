import asyncio
import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage

from exceptions.chat import (
    ChatAccessDeniedError,
    ChatNotFoundError,
    UnsupportedChatModelError,
)
from exceptions.document import CollectionMetaNotFoundError
from models import Chat, User
from services.agent.agent_orchestrator import AgentChatOrchestrator, _extract_citations


def _make_orchestrator(**overrides):
    deps = dict(
        chat_repository=AsyncMock(),
        chat_model_registry=MagicMock(),
        collection_meta_repository=AsyncMock(),
        retrieval_service=AsyncMock(),
        usage_stats_service=AsyncMock(),
        log_repository=AsyncMock(),
        langfuse_handler=None,
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


def _fake_graph(messages: list):
    graph = MagicMock()
    graph.ainvoke = AsyncMock(return_value={"messages": messages})
    return graph


def _tool_message(**kwargs) -> ToolMessage:
    defaults = dict(content="{}", name="search_documents", tool_call_id="t1")
    defaults.update(kwargs)
    return ToolMessage(**defaults)


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
    # 검색 도구 결과 → 인용 추출, 여러 AIMessage의 사용량 합산, 메시지 2건 저장,
    # 사용량 기록 순서로 한 턴을 조립한다.
    orchestrator, deps = _make_orchestrator()
    deps["chat_repository"].get_chat.return_value = _chat()

    messages = [
        HumanMessage(content="질문"),
        AIMessage(
            content="",
            usage_metadata={
                "input_tokens": 7,
                "output_tokens": 0,
                "total_tokens": 7,
            },
        ),
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
        AIMessage(
            content="답변",
            usage_metadata={
                "input_tokens": 10,
                "output_tokens": 5,
                "total_tokens": 15,
                "output_token_details": {"reasoning": 2},
            },
        ),
    ]

    with patch(
        "services.agent.agent_orchestrator.create_agent",
        return_value=_fake_graph(messages),
    ):
        result = asyncio.run(
            orchestrator.send_message(
                AsyncMock(), chat_id="c1", query="질문", requester=_user()
            )
        )

    assert result.content == "답변"
    assert len(result.citations) == 1
    assert result.citations[0].chunk_id == "c1"
    assert result.citations[0].source_type == "document"
    assert deps["chat_repository"].add_message.await_count == 2
    deps["log_repository"].create_chat_usage_log.assert_awaited_once()
    _, kwargs = deps["log_repository"].create_chat_usage_log.call_args
    assert kwargs["conversation_id"] == "c1"
    assert kwargs["input_tokens"] == 17  # 7 + 10, summed across both AIMessages
    assert kwargs["output_tokens"] == 5
    assert kwargs["reasoning_tokens"] == 2


def test_send_message_success_with_tool_calls_saved_to_log():
    # 에이전트가 호출한 도구(이름+인자)를 턴마다 한 번에 로그 테이블로 저장한다.
    orchestrator, deps = _make_orchestrator()
    deps["chat_repository"].get_chat.return_value = _chat()

    messages = [
        HumanMessage(content="질문"),
        AIMessage(
            content="",
            tool_calls=[
                {
                    "name": "search_documents",
                    "args": {"query": "질문", "collection_name": "docs"},
                    "id": "call_1",
                    "type": "tool_call",
                }
            ],
        ),
        _tool_message(content=json.dumps({"results": []})),
        AIMessage(content="답변"),
    ]

    with patch(
        "services.agent.agent_orchestrator.create_agent",
        return_value=_fake_graph(messages),
    ):
        asyncio.run(
            orchestrator.send_message(
                AsyncMock(), chat_id="c1", query="질문", requester=_user()
            )
        )

    deps["log_repository"].create_agent_tool_call_logs.assert_awaited_once()
    _, kwargs = deps["log_repository"].create_agent_tool_call_logs.call_args
    assert kwargs["conversation_id"] == "c1"
    assert kwargs["tool_calls"] == [
        {"name": "search_documents", "args": {"query": "질문", "collection_name": "docs"}}
    ]


def test_send_message_success_with_langfuse_handler_included():
    # langfuse_handler가 설정되면 콜백 목록에 포함되고, 아니면 빈 목록이다.
    handler = MagicMock()
    orchestrator, deps = _make_orchestrator(langfuse_handler=handler)
    deps["chat_repository"].get_chat.return_value = _chat()
    graph = _fake_graph([AIMessage(content="답변")])

    with patch("services.agent.agent_orchestrator.create_agent", return_value=graph):
        asyncio.run(
            orchestrator.send_message(
                AsyncMock(), chat_id="c1", query="질문", requester=_user()
            )
        )

    _, kwargs = graph.ainvoke.call_args
    assert kwargs["config"]["callbacks"] == [handler]
    assert kwargs["config"]["metadata"]["langfuse_session_id"] == "c1"
    assert kwargs["config"]["metadata"]["langfuse_user_id"] == "1"


def test_send_message_failed_with_missing_chat():
    # 존재하지 않는 chat_id면 ChatNotFoundError
    orchestrator, deps = _make_orchestrator()
    deps["chat_repository"].get_chat.return_value = None

    with pytest.raises(ChatNotFoundError):
        asyncio.run(
            orchestrator.send_message(
                AsyncMock(), chat_id="missing", query="질문", requester=_user()
            )
        )


def test_send_message_failed_with_other_users_chat():
    # IDOR 방지: 채팅 소유자가 아니면 접근 거부
    orchestrator, deps = _make_orchestrator()
    deps["chat_repository"].get_chat.return_value = _chat(owner_id=99)

    with pytest.raises(ChatAccessDeniedError):
        asyncio.run(
            orchestrator.send_message(
                AsyncMock(), chat_id="c1", query="질문", requester=_user(user_id=1)
            )
        )


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
