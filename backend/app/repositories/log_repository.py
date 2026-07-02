from datetime import datetime

from sqlalchemy.ext.asyncio import AsyncSession

from models import DocumentManageLog, DocumentOperation


class LogRepository:
    """
    로그 관리
    """

    def __init__(self) -> None:
        pass

    async def create_document_manage_log(
        self,
        db: AsyncSession,
        *,
        operation: DocumentOperation,
        collection_name: str,
        status: str,
        started_at: datetime,
        finished_at: datetime,
        filename: str | None = None,
        requester_id: int | None = None,
        requester_email: str | None = None,
        document_id: str | None = None,
        chunk_count: int | None = None,
    ) -> DocumentManageLog:
        """
        문서 처리 요청 로그 저장

        Parameters:
            db(AsyncSession): DB 세션
            operation(DocumentOperation): 요청 타입(insert/update/delete)
            collection_name(str): 대상 컬렉션
            status(str): 처리 상태(success/failed)
            started_at(datetime): 요청 시작 시각
            finished_at(datetime): 요청 종료 시각
            filename(str | None): 문서 파일명(삭제 등 미상 시 None)
            requester_id(int | None): 요청자 user id
            requester_email(str | None): 요청자 이메일
            document_id(str | None): 대상 문서 id(삽입 실패 시 None)
            chunk_count(int | None): 적재된 청크 수(삽입 외 None)

        Returns:
            DocumentManageLog: 저장된 로그
        """
        log = DocumentManageLog(
            operation=operation.value,
            collection_name=collection_name,
            filename=filename,
            requester_id=requester_id,
            requester_email=requester_email,
            status=status,
            started_at=started_at,
            finished_at=finished_at,
            document_id=document_id,
            chunk_count=chunk_count,
        )
        db.add(log)
        await db.commit()
        await db.refresh(log)
        return log
