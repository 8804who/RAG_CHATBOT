from sqlalchemy import delete, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from models import DocumentRecord, DocumentStatus


class DocumentStatusRepository:
    """
    문서 인제스트 상태 관리.

    업로드 endpoint가 레코드를 생성 후 워커들이 단계별로 상태를 갱신
    """

    def __init__(self) -> None:
        pass

    async def create(
        self,
        db: AsyncSession,
        *,
        document_id: str,
        collection_name: str,
        filename: str,
        requester_id: int | None = None,
        requester_email: str | None = None,
    ) -> DocumentRecord:
        """
        UPLOADED 상태로 문서 레코드 생성

        Parameters:
            db(AsyncSession): DB 세션
            document_id(str): 문서 id
            collection_name(str): 대상 컬렉션
            filename(str): 문서 파일명
            requester_id(int | None): 요청자 user id
            requester_email(str | None): 요청자 이메일

        Returns:
            DocumentRecord: 생성된 상태 레코드
        """
        record = DocumentRecord(
            document_id=document_id,
            collection_name=collection_name,
            filename=filename,
            requester_id=requester_id,
            requester_email=requester_email,
            status=DocumentStatus.UPLOADED.value,
        )
        db.add(record)
        await db.commit()
        await db.refresh(record)
        return record

    async def get(self, db: AsyncSession, document_id: str) -> DocumentRecord | None:
        """
        문서 상태 레코드 조회

        Parameters:
            db(AsyncSession): DB 세션
            document_id(str): 조회할 문서 id

        Returns:
            DocumentRecord | None: 상태 레코드(없으면 None)
        """
        stmt = select(DocumentRecord).where(DocumentRecord.document_id == document_id)
        result = await db.execute(stmt)
        return result.scalar_one_or_none()

    async def set_status(
        self, db: AsyncSession, document_id: str, status: DocumentStatus
    ) -> None:
        """
        문서 상태 갱신

        Parameters:
            db(AsyncSession): DB 세션
            document_id(str): 대상 문서 id
            status(DocumentStatus): 새 상태
        """
        stmt = (
            update(DocumentRecord)
            .where(DocumentRecord.document_id == document_id)
            .values(status=status.value)
        )
        await db.execute(stmt)
        await db.commit()

    async def set_total_chunks(
        self, db: AsyncSession, document_id: str, total_chunks: int
    ) -> None:
        """
        총 청크 수 기록 + 상태를 PARSING으로 전환(Parser 단계 완료)

        Parameters:
            db(AsyncSession): DB 세션
            document_id(str): 대상 문서 id
            total_chunks(int): 청킹으로 생성된 총 청크 수
        """
        stmt = (
            update(DocumentRecord)
            .where(DocumentRecord.document_id == document_id)
            .values(total_chunks=total_chunks, status=DocumentStatus.PARSING.value)
        )
        await db.execute(stmt)
        await db.commit()

    async def increment_indexed(
        self, db: AsyncSession, document_id: str
    ) -> tuple[int, int | None]:
        """
        적재 완료 청크 수를 1 증가, 모두 완료 시 INDEXED로 전환.

        Parameters:
            db(AsyncSession): DB 세션
            document_id(str): 대상 문서 id

        Returns:
            tuple[int, int | None]: (증가 후 indexed_chunks, total_chunks)
        """
        stmt = (
            update(DocumentRecord)
            .where(DocumentRecord.document_id == document_id)
            .values(indexed_chunks=DocumentRecord.indexed_chunks + 1)
            .returning(DocumentRecord.indexed_chunks, DocumentRecord.total_chunks)
        )
        result = await db.execute(stmt)
        indexed_chunks, total_chunks = result.one()

        if total_chunks is not None and indexed_chunks >= total_chunks:
            await db.execute(
                update(DocumentRecord)
                .where(DocumentRecord.document_id == document_id)
                .values(status=DocumentStatus.INDEXED.value)
            )
        await db.commit()
        return indexed_chunks, total_chunks

    async def delete(self, db: AsyncSession, document_id: str) -> None:
        """
        문서 상태 레코드 삭제(문서 삭제 시 Qdrant 청크와 함께 정리)

        Parameters:
            db(AsyncSession): DB 세션
            document_id(str): 삭제할 문서 id
        """
        stmt = delete(DocumentRecord).where(DocumentRecord.document_id == document_id)
        await db.execute(stmt)
        await db.commit()

    async def set_failed(self, db: AsyncSession, document_id: str, error: str) -> None:
        """
        문서를 FAILED로 표시하고 실패 사유 기록

        Parameters:
            db(AsyncSession): DB 세션
            document_id(str): 대상 문서 id
            error(str): 실패 사유(내부 로그용, 1024자 제한)
        """
        stmt = (
            update(DocumentRecord)
            .where(DocumentRecord.document_id == document_id)
            .values(status=DocumentStatus.FAILED.value, error=error[:1024])
        )
        await db.execute(stmt)
        await db.commit()
