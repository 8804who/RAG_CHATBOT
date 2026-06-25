from abc import ABC, abstractmethod

from schemes.dto.embedding import SparseVector


class SparseEncoder(ABC):
    """
    Sparse 인코더 인터페이스
    """

    @abstractmethod
    async def encode_documents(self, texts: list[str]) -> list[SparseVector]:
        """
        문서 텍스트 벡터 인코딩
        """
        ...

    @abstractmethod
    async def encode_query(self, text: str) -> SparseVector:
        """
        쿼리 텍스트 벡터 인코딩
        """
        ...
