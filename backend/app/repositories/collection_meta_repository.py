from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncSession

from models import CollectionMeta


class CollectionMetaRepository:
    """
    컬렉션 ↔ 임베딩 모델 매핑 정보 관리
    """

    def __init__(self) -> None:
        pass

    async def get(
        self, db: AsyncSession, collection_name: str
    ) -> CollectionMeta | None:
        """
        컬렉션 메타 데이터 조회

        Parameters:
            db(AsyncSession): DB 세션
            collection_name(str): 조회할 collection 이름

        Returns:
            CollectionMeta | None: 매핑 정보(없으면 None)
        """
        return await db.get(CollectionMeta, collection_name)

    async def create(
        self,
        db: AsyncSession,
        collection_name: str,
        embedding_model: str,
        dimension: int,
    ) -> CollectionMeta:
        """
        컬렉션 메타 데이터 생성

        Parameters:
            db(AsyncSession): DB 세션
            collection_name(str): collection 이름
            embedding_model(str): 고정할 임베딩 모델 이름
            dimension(int): 임베딩 차원

        Returns:
            CollectionMeta: 저장된 매핑 정보
        """
        meta = CollectionMeta(
            collection_name=collection_name,
            embedding_model=embedding_model,
            dimension=dimension,
        )
        db.add(meta)
        await db.commit()
        return meta

    async def delete(self, db: AsyncSession, collection_name: str) -> None:
        """
        컬렉션 메타 데이터 삭제

        Parameters:
            db(AsyncSession): DB 세션
            collection_name(str): 삭제할 collection 이름
        """
        await db.execute(
            delete(CollectionMeta).where(
                CollectionMeta.collection_name == collection_name
            )
        )
        await db.commit()
