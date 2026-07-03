import logging
from datetime import datetime, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from models import DocumentOperation
from repositories import DocumentStatusRepository, LogRepository
from repositories.vector_db import QdrantRepository
from schemes.dto.document import IngestPoint
from schemes.dto.embedding import SparseVector
from schemes.events import ChunkEmbeddedEvent

logger = logging.getLogger(__name__)


class IndexService:
    """
    Index 단계: 임베딩된 청크를 Qdrant에 멱등 적재하고 완료 시 문서를 INDEXED로 표시
    """

    def __init__(
        self,
        qdrant_repository: QdrantRepository,
        document_status_repository: DocumentStatusRepository,
        log_repository: LogRepository,
    ) -> None:
        self._qdrant_repository = qdrant_repository
        self._document_status_repository = document_status_repository
        self._log_repository = log_repository

    async def handle(self, db: AsyncSession, event: ChunkEmbeddedEvent) -> None:
        """
        chunks.embed 1건(임베딩된 청크)을 Qdrant에 적재하고 진행도 갱신

        Parameters:
            db(AsyncSession): DB 세션(진행도·이력 갱신용)
            event(ChunkEmbeddedEvent): 임베딩 결과 이벤트
        """
        sparse = None
        if event.sparse_indices is not None and event.sparse_values is not None:
            sparse = SparseVector(
                indices=event.sparse_indices, values=event.sparse_values
            )

        point = IngestPoint(
            id=event.chunk_id,
            dense=event.dense,
            payload={
                "document_id": event.document_id,
                "filename": event.filename,
                "chunk_index": event.chunk_index,
                "text": event.text,
                "created_at": event.created_at,
            },
            dense_vector_name=event.dense_vector_name,
            sparse=sparse,
            sparse_vector_name=event.sparse_vector_name,
        )
        await self._qdrant_repository.upsert_points(event.collection_name, [point])

        (
            indexed_chunks,
            total_chunks,
        ) = await self._document_status_repository.increment_indexed(
            db, event.document_id
        )
        logger.debug(
            "적재: document_id=%s, indexed=%d/%s",
            event.document_id,
            indexed_chunks,
            total_chunks,
        )

        if total_chunks is not None and indexed_chunks >= total_chunks:
            await self._write_success_log(db, event, total_chunks)
            logger.info(
                "인제스트 완료(INDEXED): document_id=%s, chunk_count=%d",
                event.document_id,
                total_chunks,
            )

    async def _write_success_log(
        self, db: AsyncSession, event: ChunkEmbeddedEvent, chunk_count: int
    ) -> None:
        """
        문서 인제스트 성공 이력 기록

        Parameters:
            db(AsyncSession): DB 세션
            event(ChunkEmbeddedEvent): 마지막 청크 이벤트
            chunk_count(int): 적재된 총 청크 수
        """
        record = await self._document_status_repository.get(db, event.document_id)
        started_at = record.created_at if record else datetime.now(timezone.utc)
        await self._log_repository.create_document_manage_log(
            db,
            operation=DocumentOperation.INSERT,
            collection_name=event.collection_name,
            filename=event.filename,
            requester_id=event.requester_id,
            requester_email=event.requester_email,
            status="success",
            started_at=started_at,
            finished_at=datetime.now(timezone.utc),
            document_id=event.document_id,
            chunk_count=chunk_count,
        )
