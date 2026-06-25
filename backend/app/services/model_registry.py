import logging

from clients.embedding.embedding_client import EmbeddingClient
from exceptions.embedding import UnsupportedEmbeddingModelError
from schemes.dto.embedding import RegisteredEmbeddingModel

logger = logging.getLogger(__name__)


class EmbeddingModelRegistry:
    """
    임베딩 모델 목록 관리
    """

    def __init__(
        self,
        catalog: dict[str, tuple[RegisteredEmbeddingModel, EmbeddingClient]],
    ) -> None:
        self._catalog = catalog

    def list_models(self) -> list[RegisteredEmbeddingModel]:
        """
        등록된 임베딩 모델 목록

        Returns:
            list[RegisteredEmbeddingModel]: 카탈로그 항목 목록
        """
        return [info for info, _ in self._catalog.values()]

    def get_info(self, model_name: str) -> RegisteredEmbeddingModel:
        """
        모델 정보 조회

        Parameters:
            model_name(str): 조회할 모델 이름

        Returns:
            RegisteredEmbeddingModel: 모델 메타(provider, dimension)
        """
        entry = self._catalog.get(model_name)
        if entry is None:
            raise UnsupportedEmbeddingModelError(
                message=f"embedding model '{model_name}' is not registered",
                code_path="embedding_model_registry-get_info-error",
            )
        return entry[0]

    def resolve(self, model_name: str) -> EmbeddingClient:
        """모델 이름으로 dense 임베딩 client resolve(미등록 시 예외).

        Parameters:
            model_name(str): resolve할 모델 이름

        Returns:
            EmbeddingClient: 해당 모델의 provider client
        """
        entry = self._catalog.get(model_name)
        if entry is None:
            raise UnsupportedEmbeddingModelError(
                message=f"embedding model '{model_name}' is not registered",
                code_path="embedding_model_registry-resolve-error",
            )
        return entry[1]
