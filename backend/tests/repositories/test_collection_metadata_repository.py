import asyncio
from unittest.mock import AsyncMock, MagicMock

from models import CollectionMeta
from repositories.collection_metadata_repository import CollectionMetadataRepository


def _make_db(scalar_result: object) -> AsyncMock:
    """execute().scalar_one_or_none()이 scalar_result를 반환하는 가짜 세션."""
    result = MagicMock()
    result.scalar_one_or_none.return_value = scalar_result
    db = AsyncMock()
    db.execute = AsyncMock(return_value=result)
    return db


def test_get_collection_metadata_success_with_missing_row():
    # 매핑이 없으면 예외를 던지지 않고 None을 반환한다(scalar_one -> scalar_one_or_none 수정 확인).
    repo = CollectionMetadataRepository()
    db = _make_db(None)

    result = asyncio.run(repo.get_collection_metadata(db, "missing"))

    assert result is None


def test_get_collection_metadata_success_with_existing_row():
    # 매핑이 있으면 CollectionMeta를 그대로 반환한다.
    repo = CollectionMetadataRepository()
    meta = CollectionMeta(
        collection_name="docs", embedding_model="BAAI/bge-m3", dimension=1024
    )
    db = _make_db(meta)

    result = asyncio.run(repo.get_collection_metadata(db, "docs"))

    assert result is meta


def test_list_all_success_with_multiple_rows():
    # 전체 컬렉션 메타 목록을 반환한다(에이전트의 검색 대상 후보 나열용).
    repo = CollectionMetadataRepository()
    metas = [
        CollectionMeta(collection_name="docs", embedding_model="m", dimension=1),
        CollectionMeta(collection_name="hr", embedding_model="m", dimension=1),
    ]
    scalars = MagicMock()
    scalars.all.return_value = metas
    result_mock = MagicMock()
    result_mock.scalars.return_value = scalars
    db = AsyncMock()
    db.execute = AsyncMock(return_value=result_mock)

    result = asyncio.run(repo.list_all(db))

    assert result == metas
