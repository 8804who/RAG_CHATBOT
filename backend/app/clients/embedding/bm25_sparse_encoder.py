import anyio

from fastembed import SparseTextEmbedding

from schemes.dto.embedding import SparseVector
from clients.embedding.sparse_encoder import SparseEncoder


class BM25SparseEncoder(SparseEncoder):
    """
    BM25 기반 Sparse 인코더
    """

    def __init__(self, model_name: str = "Qdrant/bm25") -> None:
        self._model_name = model_name
        self._model = SparseTextEmbedding(model_name=self._model_name)

    async def encode_documents(self, texts: list[str]) -> list[SparseVector]:
        def _run() -> list[SparseVector]:
            return [
                SparseVector(
                    indices=embedding.indices.tolist(),
                    values=embedding.values.tolist(),
                )
                for embedding in self._model.embed(texts)
            ]

        return await anyio.to_thread.run_sync(_run)

    async def encode_query(self, text: str) -> SparseVector:
        def _run() -> SparseVector:
            embedding = next(iter(self._model.query_embed([text])))
            return SparseVector(
                indices=embedding.indices.tolist(),
                values=embedding.values.tolist(),
            )

        return await anyio.to_thread.run_sync(_run)
