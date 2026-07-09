from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from models import ChatUsageLog, DocumentManageLog, DocumentOperation
from schemes.dto.usage import ChatUsageRow, EmbeddingUsageRow


class LogRepository:
    """
    로그 관리(문서 관리 이력 + 채팅 토큰 사용 이력)
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
        embedding_model: str | None = None,
        embedding_tokens: int | None = None,
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
            embedding_model(str | None): 사용한 임베딩 모델(삽입 외 None)
            embedding_tokens(int | None): 소비한 임베딩 토큰 수(로컬 모델 0)

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
            embedding_model=embedding_model,
            embedding_tokens=embedding_tokens,
        )
        db.add(log)
        await db.commit()
        await db.refresh(log)
        return log

    async def has_insert_success_log(self, db: AsyncSession, document_id: str) -> bool:
        """
        해당 문서의 인제스트 성공 로그가 이미 존재하는지 확인

        Kafka at-least-once 재전송/워커 재시도로 마지막 청크 이벤트가 중복 처리될
        수 있어, 성공 로그를 쓰기 전 중복 여부를 먼저 확인한다.

        Parameters:
            db(AsyncSession): DB 세션
            document_id(str): 확인할 문서 id

        Returns:
            bool: insert/success 로그 존재 여부
        """
        stmt = (
            select(DocumentManageLog.id)
            .where(
                DocumentManageLog.document_id == document_id,
                DocumentManageLog.operation == DocumentOperation.INSERT.value,
                DocumentManageLog.status == "success",
            )
            .limit(1)
        )
        result = await db.execute(stmt)
        return result.scalar_one_or_none() is not None

    async def create_chat_usage_log(
        self,
        db: AsyncSession,
        *,
        model: str,
        input_tokens: int,
        output_tokens: int,
        reasoning_tokens: int = 0,
        requester_id: int | None = None,
        requester_email: str | None = None,
        collection_name: str | None = None,
        conversation_id: str | None = None,
    ) -> ChatUsageLog:
        """
        채팅 토큰 사용 이력 저장

        Parameters:
            db(AsyncSession): DB 세션
            model(str): 채팅 모델 이름
            input_tokens(int): 입력(prompt) 토큰 수
            output_tokens(int): 출력(completion) 토큰 수
            reasoning_tokens(int): 추론(thinking) 토큰 수
            requester_id(int | None): 요청자 user id
            requester_email(str | None): 요청자 이메일
            collection_name(str | None): 질의 대상 컬렉션
            conversation_id(str | None): 대화 식별자

        Returns:
            ChatUsageLog: 저장된 사용 이력
        """
        log = ChatUsageLog(
            requester_id=requester_id,
            requester_email=requester_email,
            model=model,
            collection_name=collection_name,
            conversation_id=conversation_id,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            reasoning_tokens=reasoning_tokens,
        )
        db.add(log)
        await db.commit()
        await db.refresh(log)
        return log

    async def aggregate_embedding_usage(
        self, db: AsyncSession, requester_id: int
    ) -> list[EmbeddingUsageRow]:
        """
        사용자 임베딩 토큰 사용량 모델별 집계

        Parameters:
            db(AsyncSession): DB 세션
            requester_id(int): 집계 대상 user id

        Returns:
            list[EmbeddingUsageRow]: 모델별 (토큰 합, 문서 수)
        """
        stmt = (
            select(
                DocumentManageLog.embedding_model,
                func.coalesce(func.sum(DocumentManageLog.embedding_tokens), 0),
                func.count(DocumentManageLog.id),
            )
            .where(
                DocumentManageLog.requester_id == requester_id,
                DocumentManageLog.operation == DocumentOperation.INSERT.value,
                DocumentManageLog.status == "success",
                DocumentManageLog.embedding_model.is_not(None),
            )
            .group_by(DocumentManageLog.embedding_model)
        )
        result = await db.execute(stmt)
        return [
            EmbeddingUsageRow(
                model=model, total_tokens=int(tokens), document_count=int(count)
            )
            for model, tokens, count in result.all()
        ]

    async def aggregate_chat_usage(
        self, db: AsyncSession, requester_id: int
    ) -> list[ChatUsageRow]:
        """
        사용자 채팅 토큰 사용량 모델별 집계

        Parameters:
            db(AsyncSession): DB 세션
            requester_id(int): 집계 대상 user id

        Returns:
            list[ChatUsageRow]: 모델별 (입력·출력·추론 토큰 합, 메시지 수)
        """
        stmt = (
            select(
                ChatUsageLog.model,
                func.coalesce(func.sum(ChatUsageLog.input_tokens), 0),
                func.coalesce(func.sum(ChatUsageLog.output_tokens), 0),
                func.coalesce(func.sum(ChatUsageLog.reasoning_tokens), 0),
                func.count(ChatUsageLog.id),
            )
            .where(ChatUsageLog.requester_id == requester_id)
            .group_by(ChatUsageLog.model)
        )
        result = await db.execute(stmt)
        return [
            ChatUsageRow(
                model=model,
                input_tokens=int(input_tokens),
                output_tokens=int(output_tokens),
                reasoning_tokens=int(reasoning_tokens),
                message_count=int(count),
            )
            for model, input_tokens, output_tokens, reasoning_tokens, count in (
                result.all()
            )
        ]
