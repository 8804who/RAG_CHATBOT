from qdrant_client import models

from clients import QdrantDBClient
from exceptions.vector_db import (
    CollectionAlreadyExistsError,
    CollectionNotFoundError,
)
from repositories.vector_db.vector_db_repository import VectorDBRepository
from schemes.dto.qdrant import (
    CollectionDetail,
    CollectionSummary,
    DenseVectorDetail,
    SparseVectorDetail,
)
from schemes.requests import (
    CreateQdrantCollectionRequest,
    UpdateQdrantCollectionRequest,
)


def _enum_value(value: object) -> object:
    """Enum이면 그 value를, 아니면 값 자체를 반환(런타임 타입 분기 회피)."""
    return getattr(value, "value", value)


class QdrantRepository(VectorDBRepository):
    def __init__(self, qdrant_client: QdrantDBClient):
        self._qdrant_client = qdrant_client

    async def get_collections(self) -> list[CollectionSummary]:
        """
        Qdrant collection 목록 조회

        Returns:
            list[CollectionSummary]: collection 이름 목록
        """
        result = await self._qdrant_client.client.get_collections()
        return [CollectionSummary(name=c.name) for c in result.collections]

    async def get_collection(self, collection_name: str) -> CollectionDetail:
        """
        Qdrant collection 상세 조회

        Parameters:
            collection_name(str): 조회할 collection 이름

        Returns:
            CollectionDetail: vector 구성/최적화 설정을 담은 상세 정보
        """
        await self._ensure_exists(collection_name)
        info = await self._qdrant_client.client.get_collection(collection_name)

        params = info.config.params

        dense_vectors = {
            name: DenseVectorDetail(
                size=cfg.size,
                distance=str(_enum_value(cfg.distance)),
                on_disk=bool(cfg.on_disk),
            )
            for name, cfg in (params.vectors or {}).items()
        }

        sparse_vectors = {
            name: SparseVectorDetail(
                modifier=str(_enum_value(cfg.modifier))
                if cfg.modifier is not None
                else None,
                on_disk=bool(cfg.index.on_disk) if cfg.index else False,
            )
            for name, cfg in (params.sparse_vectors or {}).items()
        }

        optimizer = info.config.optimizer_config
        return CollectionDetail(
            name=collection_name,
            status=str(_enum_value(info.status)),
            points_count=info.points_count or 0,
            dense_vectors=dense_vectors,
            sparse_vectors=sparse_vectors,
            indexing_threshold=optimizer.indexing_threshold if optimizer else None,
            default_segment_number=optimizer.default_segment_number
            if optimizer
            else None,
        )

    async def create_collections(self, request: CreateQdrantCollectionRequest) -> bool:
        """
        Qdrant collection 생성

        Parameters:
            request(CreateQdrantCollectionRequest): 생성할 collection 정보

        Returns:
            bool: collection 생성 성공 여부
        """
        if await self._qdrant_client.client.collection_exists(request.collection_name):
            raise CollectionAlreadyExistsError(
                message=f"collection '{request.collection_name}' already exists",
                code_path="qdrant_repository-create_collections-error",
            )

        vectors_config = {
            name: models.VectorParams(
                size=cfg.size,
                distance=models.Distance(cfg.distance.value),
                on_disk=cfg.on_disk,
            )
            for name, cfg in request.dense_vectors.items()
        }
        sparse_vectors_config = {
            name: models.SparseVectorParams(
                modifier=models.Modifier(cfg.modifier.value),
                index=models.SparseIndexParams(on_disk=cfg.on_disk),
            )
            for name, cfg in request.sparse_vectors.items()
        }
        result = await self._qdrant_client.client.create_collection(
            collection_name=request.collection_name,
            vectors_config=vectors_config,
            sparse_vectors_config=sparse_vectors_config or None,
            on_disk_payload=request.on_disk_payload,
        )
        return result

    async def update_collection(
        self, collection_name: str, request: UpdateQdrantCollectionRequest
    ) -> bool:
        """
        Qdrant collection의 수정 설정 갱신

        Parameters:
            collection_name(str): 수정할 collection 이름
            request(UpdateQdrantCollectionRequest): 갱신할 설정(vector size/distance 제외)

        Returns:
            bool: 갱신 성공 여부
        """
        await self._ensure_exists(collection_name)

        kwargs: dict = {}

        if request.dense_vectors:
            vectors_config = {
                name: models.VectorParamsDiff(on_disk=cfg.on_disk)
                for name, cfg in request.dense_vectors.items()
                if cfg.on_disk is not None
            }
            if vectors_config:
                kwargs["vectors_config"] = vectors_config

        if request.sparse_vectors:
            sparse_vectors_config = {
                name: models.SparseVectorParams(
                    index=models.SparseIndexParams(on_disk=cfg.on_disk)
                )
                for name, cfg in request.sparse_vectors.items()
                if cfg.on_disk is not None
            }
            if sparse_vectors_config:
                kwargs["sparse_vectors_config"] = sparse_vectors_config

        if request.optimizers_config:
            optimizer = request.optimizers_config
            if (
                optimizer.indexing_threshold is not None
                or optimizer.default_segment_number is not None
            ):
                kwargs["optimizers_config"] = models.OptimizersConfigDiff(
                    indexing_threshold=optimizer.indexing_threshold,
                    default_segment_number=optimizer.default_segment_number,
                )

        result = await self._qdrant_client.client.update_collection(
            collection_name=collection_name,
            **kwargs,
        )
        return result

    async def delete_collection(self, collection_name: str) -> bool:
        """
        Qdrant collection 삭제

        Parameters:
            collection_name(str): 삭제할 collection 이름

        Returns:
            bool: 삭제 성공 여부
        """
        await self._ensure_exists(collection_name)
        result = await self._qdrant_client.client.delete_collection(
            collection_name=collection_name
        )
        return result

    async def _ensure_exists(self, collection_name: str) -> None:
        """collection 존재 여부 확인 후 없으면 CollectionNotFoundError 발생."""
        if not await self._qdrant_client.client.collection_exists(collection_name):
            raise CollectionNotFoundError(
                message=f"collection '{collection_name}' not found",
                code_path="qdrant_repository-_ensure_exists-error",
            )
