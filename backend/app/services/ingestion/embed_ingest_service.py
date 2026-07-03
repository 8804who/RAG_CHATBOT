import logging
from datetime import datetime, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from clients import KafkaProducerClient
from models import DocumentStatus
from repositories import DocumentStatusRepository
from schemes.events import (
    TOPIC_CHUNKS_EMBED,
    ChunkEmbeddedEvent,
    DocumentParsedEvent,
)
from services.embedding import EmbeddingService

logger = logging.getLogger(__name__)


class EmbedIngestService:
    """
    Embed 단계: 청크를 컬렉션 고정 모델로 임베딩해 chunks.embed로 발행.

    (MVP: 메시지당 청크 1개를 임베딩한다. 처리량 최적화를 위한 마이크로 배치는
    후속 과제 — RAG_ARCHITECTURE §11.2.)
    """

    def __init__(
        self,
        embedding_service: EmbeddingService,
        document_status_repository: DocumentStatusRepository,
        kafka_producer: KafkaProducerClient,
    ) -> None:
        self._embedding_service = embedding_service
        self._document_status_repository = document_status_repository
        self._kafka_producer = kafka_producer

    async def handle(self, db: AsyncSession, event: DocumentParsedEvent) -> None:
        """
        documents.parsed 1건(청크 1개)을 임베딩해 chunks.embed로 발행.

        Parameters:
            db(AsyncSession): DB 세션(상태 갱신용)
            event(DocumentParsedEvent): 청크 이벤트(컬렉션 고정 임베딩 모델 포함)
        """
        if event.chunk_index == 0:
            # 첫 청크를 처리할 때 문서 상태를 EMBEDDING으로 전환.
            await self._document_status_repository.set_status(
                db, event.document_id, DocumentStatus.EMBEDDING
            )

        results = await self._embedding_service.embed_documents(
            event.embedding_model, [event.text], with_sparse=event.with_sparse
        )
        result = results[0]

        sparse_indices = None
        sparse_values = None
        if event.with_sparse and result.sparse is not None:
            sparse_indices = result.sparse.indices
            sparse_values = result.sparse.values

        embedded = ChunkEmbeddedEvent(
            document_id=event.document_id,
            collection_name=event.collection_name,
            filename=event.filename,
            chunk_id=event.chunk_id,
            chunk_index=event.chunk_index,
            text=event.text,
            total_chunks=event.total_chunks,
            created_at=datetime.now(timezone.utc).isoformat(),
            dense=result.dense,
            dense_vector_name=event.dense_vector_name,
            sparse_indices=sparse_indices,
            sparse_values=sparse_values,
            sparse_vector_name=event.sparse_vector_name,
            requester_id=event.requester_id,
            requester_email=event.requester_email,
        )
        await self._kafka_producer.publish(
            TOPIC_CHUNKS_EMBED, key=event.document_id, value=embedded.to_bytes()
        )
        logger.debug(
            "임베딩 완료: document_id=%s, chunk_index=%d/%d, model=%s",
            event.document_id,
            event.chunk_index,
            event.total_chunks,
            event.embedding_model,
        )
