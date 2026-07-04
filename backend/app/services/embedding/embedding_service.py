from clients.embedding.sparse_encoder import SparseEncoder
from schemes.dto.embedding import EmbeddingResult
from services.model_registry import EmbeddingModelRegistry


class EmbeddingService:
    """
    텍스트 임베딩 오케스트레이션 서비스
    """

    def __init__(
        self,
        embedding_registry: EmbeddingModelRegistry,
        sparse_encoder: SparseEncoder,
    ) -> None:
        self._embedding_registry = embedding_registry
        self._sparse_encoder = sparse_encoder

    async def embed_documents(
        self, model_name: str, texts: list[str], with_sparse: bool = True
    ) -> tuple[list[EmbeddingResult], int | None]:
        """
        문서 텍스트 임베딩

        Parameters:
            model_name(str): 임베딩 모델
            texts(list[str]): 텍스트 목록
            with_sparse(bool): sparse 동시 생성 여부

        Returns:
            tuple[list[EmbeddingResult], int | None]: (텍스트 별 임베딩 결과,
                dense provider가 소비한 토큰 수; 로컬 모델은 None)
        """
        if not texts:
            return [], None

        client = self._embedding_registry.resolve(model_name)
        dense = await client.embed_documents(texts)
        sparse_vectors = (
            await self._sparse_encoder.encode_documents(texts)
            if with_sparse
            else [None] * len(texts)
        )
        results = [
            EmbeddingResult(dense=vector, sparse=sparse)
            for vector, sparse in zip(dense.vectors, sparse_vectors, strict=True)
        ]
        return results, dense.tokens

    async def embed_query(
        self, model_name: str, text: str, with_sparse: bool = True
    ) -> EmbeddingResult:
        """
        질의 텍스트 임베딩

        Parameters:
            model_name(str): 임베딩 모델
            text(str): 질의
            with_sparse(bool): sparse 동시 생성 여부

        Returns:
            EmbeddingResult: 임베딩 결과
        """
        client = self._embedding_registry.resolve(model_name)
        dense = await client.embed_query(text)
        sparse = await self._sparse_encoder.encode_query(text) if with_sparse else None
        return EmbeddingResult(dense=dense, sparse=sparse)
