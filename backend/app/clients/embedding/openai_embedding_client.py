from openai import AsyncOpenAI

from clients.embedding.embedding_client import EmbeddingClient


class OpenAIEmbeddingClient(EmbeddingClient):
    """OpenAI text-embedding-3-* dense 임베딩 구현.

    AsyncOpenAI는 네이티브 async이므로 스레드풀이 필요 없다. 클라이언트는
    애플리케이션 시작 시 warmup으로 생성한다(원격 API라 로컬 모델 로딩은
    없고 httpx 풀만 준비한다). API 키가 없으면 warmup이 실패하므로,
    레지스트리가 개별 provider 단위로 격리해 시작을 막지 않는다.
    """

    def __init__(self, model_name: str, dimension: int, api_key: str | None) -> None:
        self._model_name = model_name
        self._dimension = dimension
        self._api_key = api_key
        self._client = AsyncOpenAI(api_key=self._api_key)

    @property
    def model_name(self) -> str:
        return self._model_name

    @property
    def dimension(self) -> int:
        return self._dimension

    async def embed_documents(self, texts: list[str]) -> list[list[float]]:
        response = await self._client.embeddings.create(model=self._model_name, input=texts)
        return [item.embedding for item in response.data]

    async def embed_query(self, text: str) -> list[float]:
        response = await self.client.embeddings.create(model=self._model_name, input=[text])
        return response.data[0].embedding
