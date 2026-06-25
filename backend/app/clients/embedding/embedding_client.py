from abc import ABC, abstractmethod


class EmbeddingClient(ABC):
    """Dense 임베딩 provider 인터페이스.

    provider를 추가 시, 인터페이스 구현 후 EmbeddingModelRegistry에 등록
    """

    @property
    @abstractmethod
    def model_name(self) -> str:
        """
        모델 식별자
        """
        ...

    @property
    @abstractmethod
    def dimension(self) -> int:
        """
        dense 벡터 차원
        """
        ...

    @abstractmethod
    async def embed_documents(self, texts: list[str]) -> list[list[float]]:
        """
        문서 텍스트들을 dense 벡터로 임베딩

        Parameters:
            texts(list[str]): 임베딩할 텍스트 목록

        Returns:
            list[list[float]]: 입력 순서와 동일한 dense 벡터 목록
        """
        ...

    @abstractmethod
    async def embed_query(self, text: str) -> list[float]:
        """
        쿼리 텍스트를 dense 벡터로 임베딩

        Parameters:
            text(str): 임베딩할 질의

        Returns:
            list[float]: dense 벡터
        """
        ...