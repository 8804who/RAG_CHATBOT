import logging
from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy.ext.asyncio import AsyncSession

from exceptions.document import (
    CollectionMetaNotFoundError,
    DenseVectorNotConfiguredError,
    EmptyDocumentError,
)
from repositories import CollectionMetadataRepository, LogRepository
from repositories.vector_db import QdrantRepository
from schemes.dto.document import DocumentChunk, DocumentSummary, IngestPoint
from services.embedding import EmbeddingService
from utils.chunker import chunk_text

logger = logging.getLogger(__name__)


class DocumentService:
    """
    문서 인제스트, 컬렉션 내부 문서 조회 오케스트레이션 서비스
    """

    def __init__(
        self,
        qdrant_repository: QdrantRepository,
        embedding_service: EmbeddingService,
        collection_meta_repository: CollectionMetadataRepository,
        log_repository: LogRepository,
    ) -> None:
        self._qdrant_repository = qdrant_repository
        self._embedding_service = embedding_service
        self._collection_meta_repository = collection_meta_repository
        self._log_repository = log_repository

    async def ingest(
        self,
        db: AsyncSession,
        collection_name: str,
        filename: str,
        content: str,
        requester_id: int | None = None,
        requester_email: str | None = None,
    ) -> DocumentSummary:
        """
        문서를 청킹·임베딩 후 컬렉션 적재.

        시작·종료 시각, 요청자, 파일명, 컬렉션 정보를 인제스트 이력으로 DB에 기록한다
        (성공·실패 모두 기록).

        Parameters:
            db(AsyncSession): DB 세션(컬렉션 임베딩 모델 조회·이력 저장용)
            collection_name(str): 적재 대상 컬렉션
            filename(str): 문서 파일명(표시·그룹 라벨)
            content(str): 문서 텍스트
            requester_id(int | None): 요청자 user id
            requester_email(str | None): 요청자 이메일

        Returns:
            DocumentSummary: 생성된 문서 id·청크 수 요약
        """
        started_at = datetime.now(timezone.utc)
        logger.info(
            "ingest 시작: collection=%s, filename=%s, requester=%s, content_length=%d",
            collection_name,
            filename,
            requester_email,
            len(content),
        )

        try:
            summary = await self._do_ingest(db, collection_name, filename, content)
        except Exception:
            logger.exception(
                "ingest 실패: collection=%s, filename=%s, requester=%s",
                collection_name,
                filename,
                requester_email,
            )
            await self._log_repository.create_ingest_log(
                db,
                collection_name=collection_name,
                filename=filename,
                requester_id=requester_id,
                requester_email=requester_email,
                status="failed",
                started_at=started_at,
                finished_at=datetime.now(timezone.utc),
            )
            raise

        finished_at = datetime.now(timezone.utc)
        logger.info(
            "ingest 완료: collection=%s, filename=%s, document_id=%s, chunk_count=%d",
            collection_name,
            filename,
            summary.document_id,
            summary.chunk_count,
        )
        await self._log_repository.create_ingest_log(
            db,
            collection_name=collection_name,
            filename=filename,
            requester_id=requester_id,
            requester_email=requester_email,
            status="success",
            started_at=started_at,
            finished_at=finished_at,
            document_id=summary.document_id,
            chunk_count=summary.chunk_count,
        )
        return summary

    async def _do_ingest(
        self, db: AsyncSession, collection_name: str, filename: str, content: str
    ) -> DocumentSummary:
        """
        문서 청킹·임베딩·적재 핵심 로직(이력 기록은 ingest가 담당).

        Parameters:
            db(AsyncSession): DB 세션(컬렉션 임베딩 모델 조회용)
            collection_name(str): 적재 대상 컬렉션
            filename(str): 문서 파일명
            content(str): 문서 텍스트

        Returns:
            DocumentSummary: 생성된 문서 id·청크 수 요약
        """
        meta = await self._collection_meta_repository.get_collection_metadata(
            db, collection_name
        )
        if meta is None:
            raise CollectionMetaNotFoundError(
                message=f"collection '{collection_name}' has no embedding mapping",
                code_path="document_service-ingest-error",
            )

        # 컬렉션 존재 확인 + dense/sparse vector 이름 확보(적재 시 이름 일치 필요).
        detail = await self._qdrant_repository.get_collection(collection_name)
        dense_name = next(iter(detail.dense_vectors), None)
        if dense_name is None:
            raise DenseVectorNotConfiguredError(
                message=f"collection '{collection_name}' has no dense vector",
                code_path="document_service-ingest-error",
            )
        sparse_name = next(iter(detail.sparse_vectors), None)
        with_sparse = sparse_name is not None

        chunks = chunk_text(content)
        if not chunks:
            raise EmptyDocumentError(
                message="document produced no chunks",
                code_path="document_service-ingest-error",
            )
        logger.info(
            "청킹 완료: collection=%s, filename=%s, chunk_count=%d",
            collection_name,
            filename,
            len(chunks),
        )

        results = await self._embedding_service.embed_documents(
            meta.embedding_model, chunks, with_sparse=with_sparse
        )
        logger.info(
            "임베딩 완료: collection=%s, filename=%s, model=%s, with_sparse=%s",
            collection_name,
            filename,
            meta.embedding_model,
            with_sparse,
        )

        document_id = uuid4().hex
        created_at = datetime.now(timezone.utc).isoformat()
        points = [
            IngestPoint(
                id=uuid4().hex,
                dense=result.dense,
                payload={
                    "document_id": document_id,
                    "filename": filename,
                    "chunk_index": index,
                    "text": chunk,
                    "created_at": created_at,
                },
                dense_vector_name=dense_name,
                sparse=result.sparse if with_sparse else None,
                sparse_vector_name=sparse_name,
            )
            for index, (chunk, result) in enumerate(zip(chunks, results, strict=True))
        ]
        await self._qdrant_repository.upsert_points(collection_name, points)

        return DocumentSummary(
            document_id=document_id,
            filename=filename,
            chunk_count=len(chunks),
            created_at=created_at,
        )

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

    async def delete_document(self, collection_name: str, document_id: str) -> None:
        """
        컬렉션에서 문서 삭제.

        Parameters:
            collection_name(str): 대상 컬렉션
            document_id(str): 삭제할 문서 id
        """
        await self._qdrant_repository.delete_by_document(collection_name, document_id)
