import json
import logging
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET

from langchain_core.tools import BaseTool, tool
from simpleeval import simple_eval
from sqlalchemy.ext.asyncio import AsyncSession

from core.config import config
from repositories import CollectionMetadataRepository
from services.retrieval import RetrievalService
from services.usage import UsageStatsService

logger = logging.getLogger(__name__)

RETRIEVAL_TOOL_NAME = "search_documents"
WEB_SEARCH_TOOL_NAME = "tavily_search"
ARXIV_SEARCH_TOOL_NAME = "arxiv_search"

_SNIPPET_LENGTH = 300
_ARXIV_API_URL = "http://export.arxiv.org/api/query"
_ARXIV_MAX_RESULTS = 5
_ATOM_NS = "{http://www.w3.org/2005/Atom}"


def _chunks_to_json(chunks, collection_name: str) -> str:
    """검색된 청크 목록을 도구 응답용 JSON 문자열로 직렬화한다."""
    results = [
        {
            "chunk_id": chunk.chunk_id,
            "document_id": chunk.document_id,
            "filename": chunk.filename,
            "collection_name": collection_name,
            "snippet": chunk.text[:_SNIPPET_LENGTH],
        }
        for chunk in chunks
    ]
    return json.dumps({"results": results}, ensure_ascii=False)


async def build_retrieval_tool(
    db: AsyncSession,
    retrieval_service: RetrievalService,
    collection_meta_repository: CollectionMetadataRepository,
    allowed_collection: str | None,
) -> BaseTool:
    """
    문서 검색 도구 생성

    allowed_collection이 주어지면(채팅에 컬렉션이 고정된 경우) 해당 컬렉션
    에만 검색을 제한한 단일 인자 도구를 만든다. None이면(에이전트가 검색
    대상을 고르는 경우) 인제스트된 모든 컬렉션의 이름+설명을 도구 설명에
    나열하고, 모델이 collection_name을 골라 넘기는 도구를 만든다.

    Parameters:
        db(AsyncSession): DB 세션(요청 범위, 클로저로 캡처)
        retrieval_service(RetrievalService): 하이브리드 검색 서비스(재사용)
        collection_meta_repository(CollectionMetadataRepository): 컬렉션 메타 조회용
        allowed_collection(str | None): 고정된 컬렉션 이름 또는 None

    Returns:
        BaseTool: 검색 도구(이름은 항상 "search_documents")
    """
    if allowed_collection is not None:

        @tool(RETRIEVAL_TOOL_NAME)
        async def search_documents_pinned(query: str) -> str:
            """지식베이스에서 질의와 관련된 문서를 검색한다."""
            chunks = await retrieval_service.retrieve(db, allowed_collection, query)
            return _chunks_to_json(chunks, allowed_collection)

        return search_documents_pinned

    metas = await collection_meta_repository.list_all(db)
    if metas:
        catalog_lines = "\n".join(
            f"- {meta.collection_name}: {meta.description or '(설명 없음)'}"
            for meta in metas
        )
    else:
        catalog_lines = "(등록된 컬렉션이 없습니다)"

    description = (
        "지식베이스에서 질의와 관련된 문서를 검색한다. "
        "collection_name은 반드시 다음 중 하나여야 한다:\n" + catalog_lines
    )

    @tool(RETRIEVAL_TOOL_NAME, description=description)
    async def search_documents_routed(collection_name: str, query: str) -> str:
        chunks = await retrieval_service.retrieve(db, collection_name, query)
        return _chunks_to_json(chunks, collection_name)

    return search_documents_routed


def build_calculator_tool() -> BaseTool:
    """
    계산기 도구 생성

    임의 코드 실행이 아닌 simpleeval의 제한된 산술 평가만 지원한다(샌드박스
    없이 API 프로세스에서 직접 실행되므로 코드 실행 도구는 보안 위험).

    Returns:
        BaseTool: 계산기 도구
    """

    @tool
    def calculate(expression: str) -> str:
        """사칙연산 등 수식 문자열을 계산한다(코드 실행 아님, 안전한 수식 평가만 지원)."""
        try:
            result = simple_eval(expression)
        except Exception as exc:
            return f"계산 실패: {exc}"
        return str(result)

    return calculate


def build_usage_stats_tool(
    db: AsyncSession, usage_stats_service: UsageStatsService, requester_id: int
) -> BaseTool:
    """
    사용량 통계 도구 생성

    호출자 본인(requester_id)의 사용량만 조회 가능(사용자 지정 쿼리 인자
    없음 — 임의 SQL/타 사용자 데이터 접근 경로를 원천 차단).

    Parameters:
        db(AsyncSession): DB 세션(요청 범위, 클로저로 캡처)
        usage_stats_service(UsageStatsService): 기존 마이페이지 집계 서비스 재사용
        requester_id(int): 호출한 사용자 id(고정, 모델이 바꿀 수 없음)

    Returns:
        BaseTool: 사용량 통계 도구
    """

    @tool
    async def get_my_usage_stats() -> str:
        """호출한 사용자 본인의 누적 토큰 사용량·비용 통계를 조회한다. 인자가 필요 없다."""
        stats = await usage_stats_service.get_user_stats(db, requester_id)
        return json.dumps(
            {
                "chat": [
                    {
                        "model": row.model,
                        "input_tokens": row.input_tokens,
                        "output_tokens": row.output_tokens,
                        "reasoning_tokens": row.reasoning_tokens,
                        "total_tokens": row.total_tokens,
                        "cost": row.cost,
                        "currency": row.currency,
                    }
                    for row in stats.chat
                ],
                "embedding": [
                    {
                        "model": row.model,
                        "total_tokens": row.total_tokens,
                        "cost": row.cost,
                        "currency": row.currency,
                    }
                    for row in stats.embedding
                ],
                "total_cost": stats.total_cost,
                "currency": stats.currency,
            },
            ensure_ascii=False,
        )

    return get_my_usage_stats


def build_arxiv_search_tool() -> BaseTool:
    """
    arXiv 논문 검색 도구 생성

    arXiv 공개 API(export.arxiv.org, 키 불필요)를 직접 호출한다. 응답은
    tavily_search와 동일한 {url, title, content} 형태로 맞춰서, 인용 추출
    (_extract_citations)이 별도 분기 없이 재사용된다.

    Returns:
        BaseTool: arXiv 검색 도구
    """

    @tool(ARXIV_SEARCH_TOOL_NAME)
    def search_arxiv(query: str) -> str:
        """주제(topic)로 arXiv 논문을 검색해 제목/저자/초록/링크를 반환한다."""
        params = urllib.parse.urlencode(
            {
                "search_query": f"all:{query}",
                "start": 0,
                "max_results": _ARXIV_MAX_RESULTS,
            }
        )
        try:
            with urllib.request.urlopen(
                f"{_ARXIV_API_URL}?{params}", timeout=10
            ) as response:
                feed = ET.fromstring(response.read())
        except Exception as exc:
            return f"arXiv 검색 실패: {exc}"

        results = []
        for entry in feed.findall(f"{_ATOM_NS}entry"):
            summary = (entry.findtext(f"{_ATOM_NS}summary") or "").strip()
            authors = [
                author.findtext(f"{_ATOM_NS}name", default="")
                for author in entry.findall(f"{_ATOM_NS}author")
            ]
            results.append(
                {
                    "title": (entry.findtext(f"{_ATOM_NS}title") or "").strip(),
                    "url": (entry.findtext(f"{_ATOM_NS}id") or "").strip(),
                    "content": summary[:_SNIPPET_LENGTH],
                    "authors": authors,
                    "published": entry.findtext(f"{_ATOM_NS}published"),
                }
            )
        return json.dumps({"results": results}, ensure_ascii=False)

    return search_arxiv


def build_web_search_tool() -> BaseTool | None:
    """
    웹 검색 도구 생성

    TAVILY_API_KEY가 설정되지 않았으면 도구를 생략한다(None 반환).

    Returns:
        BaseTool | None: 웹 검색 도구, 또는 설정이 없으면 None
    """
    if not config.TAVILY_API_KEY:
        return None

    from langchain_tavily import TavilySearch

    return TavilySearch(max_results=5)
