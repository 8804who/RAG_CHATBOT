from fastapi import APIRouter, Path, Depends

from dependencies.services import get_qdrant_service
from schemes.requests import (
    CreateQdrantCollectionRequest,
    UpdateQdrantCollectionRequest,
)
from schemes.responses import CollectionDetailResponse, CollectionsResponse
from services.vector_db import QdrantService

router = APIRouter(prefix="/collections", tags=["collections"])


@router.get("", response_model=CollectionsResponse)
async def get_collections(
    qdrant_service: QdrantService = Depends(get_qdrant_service),
) -> CollectionsResponse:
    """
    ### collection 목록 조회

    Response Body:
        CollectionsResponse: collection 목록
            collections: collection 항목 목록
                name: collection 이름
    """
    collections = await qdrant_service.get_collections()
    return CollectionsResponse(collections=collections)


@router.get("/{collection_name}", response_model=CollectionDetailResponse)
async def get_collection(
    collection_name: str = Path(..., min_length=1),
    qdrant_service: QdrantService = Depends(get_qdrant_service),
):
    """
    ### collection 단건 상세 조회

    Path Variables:
        collection_name(str): 조회할 collection 이름

    Response Body:
        CollectionDetailResponse: collection 상세 정보
            name: collection 이름
            status: collection 상태
            points_count: 저장된 point 수
            dense_vectors: dense vector 구성 정보
            sparse_vectors: sparse vector 구성 정보
            indexing_threshold: 인덱싱 임계치
            default_segment_number: 기본 세그먼트 수

    Error Response:
        조회한 collection이 존재하지 않을 경우: (404 Not Found, "해당 collection이 존재하지 않습니다")
    """
    result = await qdrant_service.get_collection(collection_name=collection_name)
    return result


@router.post("")
async def create_collection(
    collection_info: CreateQdrantCollectionRequest,
    qdrant_service: QdrantService = Depends(get_qdrant_service),
):
    """
    ### collection 생성

    Request Body:
        CreateQdrantCollectionRequest: 생성할 collection 정보
            collection_name: 생성할 collection 이름
            dense_vectors: dense vector 구성
            sparse_vectors: sparse vector 구성
            embedding_model: 임베딩 모델 정보
            on_disk_payload: payload 디스크 저장 여부

    Response Body:
        bool: collection 생성 성공 여부

    Error Response:
        이미 존재하는 이름으로 생성할 경우: (409 Conflict, "이미 존재하는 collection 명 입니다")
    """
    result = await qdrant_service.create_collections(collection_info=collection_info)
    return result


@router.patch("/{collection_name}")
async def update_collection(
    collection_info: UpdateQdrantCollectionRequest,
    collection_name: str = Path(..., min_length=1),
    qdrant_service: QdrantService = Depends(get_qdrant_service),
):
    """
    ### collection 수정 가능한 설정 갱신

    Path Variables:
        collection_name(str): 수정할 collection 이름

    Request Body:
        UpdateQdrantCollectionRequest: 갱신할 설정(vector size/distance 제외)
            dense_vectors: dense vector 수정 설정
            sparse_vectors: sparse vector 수정 설정
            optimizers_config: optimizer 수정 설정

    Response Body:
        bool: collection 갱신 성공 여부

    Error Response:
        수정할 collection이 존재하지 않을 경우: (404 Not Found, "해당 collection이 존재하지 않습니다")
    """
    result = await qdrant_service.update_collection(
        collection_name=collection_name, collection_info=collection_info
    )
    return result


@router.delete("/{collection_name}")
async def delete_collection(
    collection_name: str = Path(..., min_length=1),
    qdrant_service: QdrantService = Depends(get_qdrant_service),
):
    """
    ### collection 삭제

    Path Variables:
        collection_name(str): 삭제할 collection 이름

    Response Body:
        bool: collection 삭제 성공 여부

    Error Response:
        삭제할 collection이 존재하지 않을 경우: (404 Not Found, "해당 collection이 존재하지 않습니다")
    """
    result = await qdrant_service.delete_collection(collection_name=collection_name)
    return result
