from datetime import datetime

from sqlalchemy.ext.asyncio import AsyncSession

from models import IngestLog


class LogRepository:
    """
    로그 관리
    """

    def __init__(self) -> None:
        pass

    async def create_ingest_log(
        self,
        db: AsyncSession,
        *,
        collection_name: str,
        filename: str,
        requester_id: int | None,
        requester_email: str | None,
        status: str,
        started_at: datetime,
        finished_at: datetime,
        document_id: str | None = None,
        chunk_count: int | None = None,
    ) -> IngestLog:
        """
        임베딩 요청 로그 저장

        Parameters:
            db(AsyncSession): DB 세션
            collection_name(str): 적재 대상 컬렉션
            filename(str): 문서 파일명
            requester_id(int | None): 요청자 user id
            requester_email(str | None): 요청자 이메일
            status(str): 처리 상태(success/failed)
            started_at(datetime): 인제스트 시작 시각
            finished_at(datetime): 인제스트 종료 시각
            document_id(str | None): 생성된 문서 id(실패 시 None)
            chunk_count(int | None): 적재된 청크 수(실패 시 None)

        Returns:
            IngestLog: 저장된 이력
        """
        log = IngestLog(
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
