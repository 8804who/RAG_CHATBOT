from fastapi import APIRouter, Depends, Path, status
from sqlalchemy.ext.asyncio import AsyncSession

from dependencies.auth import get_current_user
from dependencies.db import get_db_session
from dependencies.services import get_document_service
from models import User
from schemes.requests import IngestDocumentRequest
from schemes.responses import (
    DocumentChunksResponse,
    DocumentSummaryResponse,
    DocumentsResponse,
)
from services.ingestion import DocumentService

router = APIRouter(prefix="/collections", tags=["documents"])


@router.post(
    "/{collection_name}/documents",
    status_code=status.HTTP_201_CREATED,
    response_model=DocumentSummaryResponse,
)
async def ingest_document(
    body: IngestDocumentRequest,
    collection_name: str = Path(..., min_length=1),
    document_service: DocumentService = Depends(get_document_service),
    db: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_user),
) -> DocumentSummaryResponse:
    """
    ### 문서 임베딩

    업로드한 문서 임베딩 후 Qdrant에 저장
    Path Variables:
        collection_name(str): 적재 대상 collection 이름

    Request Body:
        IngestDocumentRequest: 인제스트할 문서
            filename: 문서 파일명
            content: 문서 텍스트

    Response Body:
        document_id: 생성된 문서 id
        filename: 문서 파일명
        chunk_count: 생성된 청크 수
        created_at: 생성 시각

    Error Response:
        컬렉션이 존재하지 않을 경우: (404 Not Found, "해당 collection이 존재하지 않습니다")
        컬렉션의 임베딩 모델 매핑이 없을 경우: (400 Bad Request, "컬렉션의 임베딩 모델 정보를 찾을 수 없습니다")
        문서 내용이 비어 있을 경우: (400 Bad Request, "문서 내용이 비어 있습니다")
    """
    return await document_service.ingest(
        db=db,
        collection_name=collection_name,
        filename=body.filename,
        content=body.content,
        requester_id=current_user.id,
        requester_email=current_user.email,
    )


@router.get("/{collection_name}/documents", response_model=DocumentsResponse)
async def list_documents(
    collection_name: str = Path(..., min_length=1),
    document_service: DocumentService = Depends(get_document_service),
    current_user: User = Depends(get_current_user),
) -> DocumentsResponse:
    """
    ### 컬렉션 내부 문서 목록 조회

    document_id 별 문서 목록 조회

    Path Variables:
        collection_name(str): 조회 대상 collection 이름

    Response Body:
        documents: 문서 항목 목록
            document_id: 문서 id
            filename: 문서 파일명
            chunk_count: 청크 수
            created_at: 생성 시각

    Error Response:
        컬렉션이 존재하지 않을 경우: (404 Not Found, "해당 collection이 존재하지 않습니다")
    """
    documents = await document_service.list_documents(collection_name)
    return DocumentsResponse(documents=documents)


@router.get(
    "/{collection_name}/documents/{document_id}/chunks",
    response_model=DocumentChunksResponse,
)
async def get_document_chunks(
    collection_name: str = Path(..., min_length=1),
    document_id: str = Path(..., min_length=1),
    document_service: DocumentService = Depends(get_document_service),
    current_user: User = Depends(get_current_user),
) -> DocumentChunksResponse:
    """
    ### 문서 청크 목록 조회

    해당 문서의 청크 목록 반환

    Path Variables:
        collection_name(str): 조회 대상 collection 이름
        document_id(str): 조회할 문서 id

    Response Body:
        document_id: 문서 id
        chunks: 청크 항목 목록
            chunk_id
            chunk_index
            text

    Error Response:
        컬렉션이 존재하지 않을 경우: (404 Not Found, "해당 collection이 존재하지 않습니다")
    """
    chunks = await document_service.get_document_chunks(collection_name, document_id)
    return DocumentChunksResponse(document_id=document_id, chunks=chunks)


@router.delete(
    "/{collection_name}/documents/{document_id}", status_code=status.HTTP_204_NO_CONTENT
)
async def delete_document(
    collection_name: str = Path(..., min_length=1),
    document_id: str = Path(..., min_length=1),
    document_service: DocumentService = Depends(get_document_service),
    db: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_user),
) -> None:
    """
    ### 문서 삭제

    문서(document_id)에 속한 모든 청크 제거

    Path Variables:
        collection_name(str): 대상 collection 이름
        document_id(str): 삭제할 문서 id

    Response Body:
        NO CONTENT

    Error Response:
        컬렉션이 존재하지 않을 경우: (404 Not Found, "해당 collection이 존재하지 않습니다")
    """
    await document_service.delete_document(
        db=db,
        collection_name=collection_name,
        document_id=document_id,
        requester_id=current_user.id,
        requester_email=current_user.email,
    )
