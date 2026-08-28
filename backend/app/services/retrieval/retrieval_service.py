import logging

from sqlalchemy.ext.asyncio import AsyncSession

from core.constants import DEFAULT_RETRIEVAL_TOP_K
from exceptions.document import (
    CollectionMetaNotFoundError,
    DenseVectorNotConfiguredError,
)
from repositories import CollectionMetadataRepository
from repositories.vector_db import QdrantRepository
from schemes.dto.retrieval import RetrievedChunk
from services.embedding import EmbeddingService

logger = logging.getLogger(__name__)


class RetrievalService:
    """
    질의 검색(하이브리드) 오케스트레이션 서비스
    """

    def __init__(
        self,
        qdrant_repository: QdrantRepository,
        collection_meta_repository: CollectionMetadataRepository,
        embedding_service: EmbeddingService,
    ) -> None:
        self._qdrant_repository = qdrant_repository
        self._collection_meta_repository = collection_meta_repository
        self._embedding_service = embedding_service

    async def retrieve(
        self,
        db: AsyncSession,
        collection_name: str,
        query: str,
        top_k: int = DEFAULT_RETRIEVAL_TOP_K,
    ) -> list[RetrievedChunk]:
        """
        질의로 컬렉션을 하이브리드 검색해 상위 청크를 반환

        컬렉션에 고정된 임베딩 모델로 질의를 임베딩하고(인제스트 때와 동일 모델
        이어야 같은 벡터 공간이므로 검색이 유효함), dense+sparse 하이브리드
        검색(RRF)을 수행한다.

        Parameters:
            db(AsyncSession): DB 세션(컬렉션 메타 조회용)
            collection_name(str): 검색 대상 컬렉션
            query(str): 사용자 질의
            top_k(int): 반환할 청크 수

        Returns:
            list[RetrievedChunk]: 점수 순 검색 결과
        """
        meta = await self._collection_meta_repository.get_collection_metadata(
            db, collection_name
        )
        if meta is None:
            raise CollectionMetaNotFoundError(
                message=f"collection '{collection_name}' has no embedding mapping",
                code_path="retrieval_service-retrieve-error",
            )

        detail = await self._qdrant_repository.get_collection(collection_name)
        dense_name = next(iter(detail.dense_vectors), None)
        if dense_name is None:
            raise DenseVectorNotConfiguredError(
                message=f"collection '{collection_name}' has no dense vector",
                code_path="retrieval_service-retrieve-error",
            )
        sparse_name = next(iter(detail.sparse_vectors), None)

        embedded = await self._embedding_service.embed_query(
            meta.embedding_model, query, with_sparse=sparse_name is not None
        )
        points = await self._qdrant_repository.search(
            collection_name,
            dense_vector_name=dense_name,
            dense=embedded.dense,
            limit=top_k,
            sparse_vector_name=sparse_name if embedded.sparse else None,
            sparse=embedded.sparse,
        )
        chunks = [
            RetrievedChunk(
                chunk_id=point.id,
                document_id=point.payload.get("document_id", ""),
                filename=point.payload.get("filename", "(unknown)"),
                chunk_index=point.payload.get("chunk_index", 0),
                text=point.payload.get("text", ""),
                score=point.score,
            )
            for point in points
        ]
        logger.debug(
            "검색 완료: collection=%s, hybrid=%s, chunk_count=%d",
            collection_name,
            sparse_name is not None,
            len(chunks),
        )
        return chunks
