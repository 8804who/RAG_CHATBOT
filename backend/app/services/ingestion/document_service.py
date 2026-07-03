import logging
from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy.ext.asyncio import AsyncSession

from clients import KafkaProducerClient
from models import DocumentOperation, DocumentRecord
from repositories import DocumentStatusRepository, LogRepository
from repositories.vector_db import QdrantRepository
from schemes.dto.document import DocumentChunk, DocumentSummary
from schemes.events import TOPIC_DOCUMENTS_UPLOADED, DocumentUploadedEvent

logger = logging.getLogger(__name__)


class DocumentService:
    """
    문서 업로드 접수(Kafka 요청) + 컬렉션 내부 문서 조회/삭제 오케스트레이션

    업로드는 원문을 Kafka(documents.uploaded)로 발행만 하고 즉시 반환 
    실제 청킹·임베딩·적재는 Parser/Embed/Index 워커에서 처리
    """

    def __init__(
        self,
        qdrant_repository: QdrantRepository,
        kafka_producer: KafkaProducerClient,
        document_status_repository: DocumentStatusRepository,
        log_repository: LogRepository,
    ) -> None:
        self._qdrant_repository = qdrant_repository
        self._kafka_producer = kafka_producer
        self._document_status_repository = document_status_repository
        self._log_repository = log_repository

    async def accept_upload(
        self,
        db: AsyncSession,
        collection_name: str,
        filename: str,
        content: str,
        requester_id: int | None = None,
        requester_email: str | None = None,
    ) -> DocumentRecord:
        """
        문서 업로드 접수 후 인제스트 파이프라인에 비동기 요청

        Parameters:
            db(AsyncSession): DB 세션(상태 레코드 생성용)
            collection_name(str): 적재 대상 컬렉션
            filename(str): 문서 파일명
            content(str): 문서 텍스트
            requester_id(int | None): 요청자 user id
            requester_email(str | None): 요청자 이메일

        Returns:
            DocumentRecord: 생성된 문서 상태 레코드(document_id·status 보유)
        """
        document_id = uuid4().hex
        record = await self._document_status_repository.create(
            db,
            document_id=document_id,
            collection_name=collection_name,
            filename=filename,
            requester_id=requester_id,
            requester_email=requester_email,
        )

        event = DocumentUploadedEvent(
            document_id=document_id,
            collection_name=collection_name,
            filename=filename,
            content=content,
            requester_id=requester_id,
            requester_email=requester_email,
        )
        await self._kafka_producer.publish(
            TOPIC_DOCUMENTS_UPLOADED, key=document_id, value=event.to_bytes()
        )
        logger.info(
            "업로드 접수: collection=%s, filename=%s, document_id=%s, requester=%s",
            collection_name,
            filename,
            document_id,
            requester_email,
        )
        return record

    async def get_status(
        self, db: AsyncSession, document_id: str
    ) -> DocumentRecord | None:
        """
        문서 인제스트 진행 상태 조회

        Parameters:
            db(AsyncSession): DB 세션
            document_id(str): 조회할 문서 id

        Returns:
            DocumentRecord | None: 상태 레코드(없으면 None)
        """
        return await self._document_status_repository.get(db, document_id)

    async def list_documents(self, collection_name: str) -> list[DocumentSummary]:
        """
        컬렉션 내부 문서 목록 조회

        Parameters:
            collection_name(str): 조회 대상 컬렉션

        Returns:
            list[DocumentSummary]: 최신순 문서 요약 목록
        """
        points = await self._qdrant_repository.scroll_points(collection_name)

        grouped: dict[str, DocumentSummary] = {}
        for point in points:
            document_id = point.payload.get("document_id")
            if document_id is None:
                continue
            summary = grouped.get(document_id)
            if summary is None:
                grouped[document_id] = DocumentSummary(
                    document_id=document_id,
                    filename=point.payload.get("filename", "(unknown)"),
                    chunk_count=1,
                    created_at=point.payload.get("created_at"),
                )
            else:
                summary.chunk_count += 1

        return sorted(
            grouped.values(),
            key=lambda summary: summary.created_at or "",
            reverse=True,
        )

    async def get_document_chunks(
        self, collection_name: str, document_id: str
    ) -> list[DocumentChunk]:
        """
        특정 문서의 청크 목록 조회

        Parameters:
            collection_name(str): 조회 대상 컬렉션
            document_id(str): 조회할 문서 id

        Returns:
            list[DocumentChunk]: 청크 목록
        """
        points = await self._qdrant_repository.scroll_points(
            collection_name, document_id=document_id
        )
        chunks = [
            DocumentChunk(
                chunk_id=point.id,
                chunk_index=point.payload.get("chunk_index", 0),
                text=point.payload.get("text", ""),
            )
            for point in points
        ]
        return sorted(chunks, key=lambda chunk: chunk.chunk_index)

    async def delete_document(
        self,
        db: AsyncSession,
        collection_name: str,
        document_id: str,
        requester_id: int | None = None,
        requester_email: str | None = None,
    ) -> None:
        """
        컬렉션에서 문서 삭제(Qdrant 청크 + 상태 레코드 정리)

        Parameters:
            db(AsyncSession): DB 세션(상태 레코드 삭제·이력 저장용)
            collection_name(str): 대상 컬렉션
            document_id(str): 삭제할 문서 id
            requester_id(int | None): 요청자 user id
            requester_email(str | None): 요청자 이메일
        """
        started_at = datetime.now(timezone.utc)
        logger.info(
            "delete 시작: collection=%s, document_id=%s, requester=%s",
            collection_name,
            document_id,
            requester_email,
        )

        try:
            await self._qdrant_repository.delete_by_document(
                collection_name, document_id
            )
            await self._document_status_repository.delete(db, document_id)
        except Exception:
            logger.exception(
                "delete 실패: collection=%s, document_id=%s, requester=%s",
                collection_name,
                document_id,
                requester_email,
            )
            await self._log_repository.create_document_manage_log(
                db,
                operation=DocumentOperation.DELETE,
                collection_name=collection_name,
                requester_id=requester_id,
                requester_email=requester_email,
                status="failed",
                started_at=started_at,
                finished_at=datetime.now(timezone.utc),
                document_id=document_id,
            )
            raise

        logger.info(
            "delete 완료: collection=%s, document_id=%s",
            collection_name,
            document_id,
        )
        await self._log_repository.create_document_manage_log(
            db,
            operation=DocumentOperation.DELETE,
            collection_name=collection_name,
            requester_id=requester_id,
            requester_email=requester_email,
            status="success",
            started_at=started_at,
            finished_at=datetime.now(timezone.utc),
            document_id=document_id,
        )
