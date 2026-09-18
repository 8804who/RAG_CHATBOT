import asyncio
import json
from unittest.mock import AsyncMock, MagicMock, patch

from schemes.dto.retrieval import RetrievedChunk
from services.agent.tools import (
    build_arxiv_search_tool,
    build_calculator_tool,
    build_retrieval_tool,
    build_usage_stats_tool,
    build_web_search_tool,
)

_ARXIV_FEED = """<?xml version="1.0" encoding="UTF-8"?>
<feed xmlns="http://www.w3.org/2005/Atom">
  <entry>
    <id>http://arxiv.org/abs/1234.5678v1</id>
    <title>A Great Paper</title>
    <summary>This paper studies a great topic in great depth.</summary>
    <published>2024-01-01T00:00:00Z</published>
    <author><name>Jane Doe</name></author>
  </entry>
</feed>
"""


def _chunk(chunk_id: str = "c1") -> RetrievedChunk:
    return RetrievedChunk(
        chunk_id=chunk_id,
        document_id="d1",
        filename="a.txt",
        chunk_index=0,
        text="본문 내용입니다",
        score=0.9,
    )


def test_build_retrieval_tool_success_with_pinned_collection():
    # 컬렉션이 고정된 채팅은 query만 받는 단일 인자 도구가 만들어진다.
    db = AsyncMock()
    retrieval_service = AsyncMock()
    retrieval_service.retrieve.return_value = [_chunk()]
    meta_repository = AsyncMock()

    tool = asyncio.run(
        build_retrieval_tool(db, retrieval_service, meta_repository, "docs")
    )
    result = asyncio.run(tool.ainvoke({"query": "질문"}))

    payload = json.loads(result)
    assert payload["results"][0]["chunk_id"] == "c1"
    assert payload["results"][0]["collection_name"] == "docs"
    retrieval_service.retrieve.assert_awaited_once_with(db, "docs", "질문")
    meta_repository.list_all.assert_not_awaited()


def test_build_retrieval_tool_success_with_routed_collection():
    # 컬렉션 미지정이면 collection_name 인자를 받는 도구가 만들어지고,
    # 설명에 등록된 컬렉션 목록이 포함된다.
    retrieval_service = AsyncMock()
    retrieval_service.retrieve.return_value = [_chunk()]
    meta_repository = AsyncMock()
    meta = MagicMock(collection_name="docs", description="문서 모음")
    meta_repository.list_all.return_value = [meta]

    tool = asyncio.run(
        build_retrieval_tool(AsyncMock(), retrieval_service, meta_repository, None)
    )

    assert "docs" in tool.description
    assert "문서 모음" in tool.description

    result = asyncio.run(tool.ainvoke({"collection_name": "docs", "query": "질문"}))
    payload = json.loads(result)
    assert payload["results"][0]["collection_name"] == "docs"


def test_build_calculator_tool_success_with_valid_expression():
    # 사칙연산 수식을 정상적으로 계산한다.
    tool = build_calculator_tool()

    result = tool.invoke({"expression": "2 + 2 * 3"})

    assert result == "8"


def test_build_calculator_tool_success_with_invalid_expression():
    # 계산 불가/위험한 입력은 예외 대신 에러 메시지 문자열을 반환한다(에이전트가 재시도 가능).
    tool = build_calculator_tool()

    result = tool.invoke({"expression": "__import__('os')"})

    assert "계산 실패" in result


def test_build_usage_stats_tool_success_with_scoped_requester():
    # 호출자 본인의 사용량만 조회하며, 사용자 지정 인자를 받지 않는다.
    usage_stats_service = AsyncMock()
    stats = MagicMock()
    stats.chat = []
    stats.embedding = []
    stats.total_cost = 0.0
    stats.currency = "USD"
    usage_stats_service.get_user_stats.return_value = stats
    db = AsyncMock()

    tool = build_usage_stats_tool(db, usage_stats_service, requester_id=42)
    result = asyncio.run(tool.ainvoke({}))

    usage_stats_service.get_user_stats.assert_awaited_once_with(db, 42)
    payload = json.loads(result)
    assert payload["total_cost"] == 0.0


def test_build_arxiv_search_tool_success_with_matching_query():
    # arXiv 응답(Atom XML)을 제목/저자/초록/링크 JSON으로 변환한다.
    tool = build_arxiv_search_tool()
    fake_response = MagicMock()
    fake_response.read.return_value = _ARXIV_FEED.encode("utf-8")
    fake_response.__enter__.return_value = fake_response

    with patch("urllib.request.urlopen", return_value=fake_response) as urlopen:
        result = tool.invoke({"query": "great topic"})

    assert "all%3Agreat+topic" in urlopen.call_args[0][0]
    payload = json.loads(result)
    assert payload["results"][0]["title"] == "A Great Paper"
    assert payload["results"][0]["url"] == "http://arxiv.org/abs/1234.5678v1"
    assert payload["results"][0]["authors"] == ["Jane Doe"]


def test_build_arxiv_search_tool_success_with_network_error():
    # 네트워크 오류는 예외 대신 에러 메시지 문자열을 반환한다(에이전트가 재시도 가능).
    tool = build_arxiv_search_tool()

    with patch("urllib.request.urlopen", side_effect=OSError("boom")):
        result = tool.invoke({"query": "anything"})

    assert "arXiv 검색 실패" in result


def test_build_web_search_tool_success_with_missing_api_key(monkeypatch):
    # TAVILY_API_KEY 미설정이면 도구를 생략한다(None).
    from core.config import config

    monkeypatch.setattr(config, "TAVILY_API_KEY", None)

    tool = build_web_search_tool()

    assert tool is None


def test_build_web_search_tool_success_with_api_key(monkeypatch):
    # TAVILY_API_KEY가 설정되면 tavily_search 도구를 만든다.
    from core.config import config

    monkeypatch.setattr(config, "TAVILY_API_KEY", "dummy-key")
    monkeypatch.setenv("TAVILY_API_KEY", "dummy-key")

    tool = build_web_search_tool()

    assert tool is not None
    assert tool.name == "tavily_search"
