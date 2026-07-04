import anyio
from fastembed import TextEmbedding

from clients.embedding.embedding_client import EmbeddingClient
from schemes.dto.embedding import DenseEmbedResult


class FastEmbedEmbeddingClient(EmbeddingClient):
    """
    FastEmbed Dense 임베딩
    """

    def __init__(self, model_name: str, dimension: int) -> None:
        self._model_name = model_name
        self._dimension = dimension
        self._model = TextEmbedding(model_name=self._model_name)

    @property
    def model_name(self) -> str:
        return self._model_name

    @property
    def dimension(self) -> int:
        return self._dimension

    async def embed_documents(self, texts: list[str]) -> DenseEmbedResult:
        def _run() -> list[list[float]]:
            return [vector.tolist() for vector in self._model.embed(texts)]

        vectors = await anyio.to_thread.run_sync(_run)
        # 로컬 모델은 API 토큰 개념이 없으므로 tokens=None.
        return DenseEmbedResult(vectors=vectors, tokens=None)

    async def embed_query(self, text: str) -> list[float]:
        def _run() -> list[float]:
            return next(iter(self._model.query_embed([text]))).tolist()

        return await anyio.to_thread.run_sync(_run)
