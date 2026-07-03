import logging
from uuid import uuid4

from sqlalchemy.ext.asyncio import AsyncSession

from clients import KafkaProducerClient
from exceptions.document import (
    CollectionMetaNotFoundError,
    DenseVectorNotConfiguredError,
    EmptyDocumentError,
)
from repositories import CollectionMetadataRepository, DocumentStatusRepository
from repositories.vector_db import QdrantRepository
from schemes.events import (
    TOPIC_DOCUMENTS_PARSED,
    DocumentParsedEvent,
    DocumentUploadedEvent,
)
from utils.chunker import chunk_text

logger = logging.getLogger(__name__)


class ParserService:
    """
    Parser 단계: 업로드 원문을 청킹해 청크당 documents.parsed 메시지로 발행
    """

    def __init__(
        self,
        qdrant_repository: QdrantRepository,
        collection_meta_repository: CollectionMetadataRepository,
        document_status_repository: DocumentStatusRepository,
        kafka_producer: KafkaProducerClient,
    ) -> None:
        self._qdrant_repository = qdrant_repository
        self._collection_meta_repository = collection_meta_repository
        self._document_status_repository = document_status_repository
        self._kafka_producer = kafka_producer

    async def handle(self, db: AsyncSession, event: DocumentUploadedEvent) -> None:
        """
        documents.uploaded 1건을 처리해 documents.parsed로 청크들을 발행.

        Parameters:
            db(AsyncSession): DB 세션(컬렉션 메타 조회·상태 갱신용)
            event(DocumentUploadedEvent): 업로드 원문 이벤트
        """
        meta = await self._collection_meta_repository.get_collection_metadata(
            db, event.collection_name
        )
        if meta is None:
            raise CollectionMetaNotFoundError(
                message=f"collection '{event.collection_name}' has no embedding mapping",
                code_path="parser_service-handle-error",
            )

        detail = await self._qdrant_repository.get_collection(event.collection_name)
        dense_name = next(iter(detail.dense_vectors), None)
        if dense_name is None:
            raise DenseVectorNotConfiguredError(
                message=f"collection '{event.collection_name}' has no dense vector",
                code_path="parser_service-handle-error",
            )
        sparse_name = next(iter(detail.sparse_vectors), None)
        with_sparse = sparse_name is not None

        chunks = chunk_text(event.content)
        if not chunks:
            raise EmptyDocumentError(
                message="document produced no chunks",
                code_path="parser_service-handle-error",
            )

        await self._document_status_repository.set_total_chunks(
            db, event.document_id, len(chunks)
        )
        logger.info(
            "파싱 완료: document_id=%s, collection=%s, chunk_count=%d",
            event.document_id,
            event.collection_name,
            len(chunks),
        )

        for index, chunk in enumerate(chunks):
            parsed = DocumentParsedEvent(
                document_id=event.document_id,
                collection_name=event.collection_name,
                filename=event.filename,
                chunk_id=uuid4().hex,
                chunk_index=index,
                text=chunk,
                total_chunks=len(chunks),
                embedding_model=meta.embedding_model,
                dense_vector_name=dense_name,
                sparse_vector_name=sparse_name,
                with_sparse=with_sparse,
                requester_id=event.requester_id,
                requester_email=event.requester_email,
            )
            await self._kafka_producer.publish(
                TOPIC_DOCUMENTS_PARSED,
                key=event.document_id,
                value=parsed.to_bytes(),
            )
