import asyncio
from unittest.mock import AsyncMock

from models import DocumentStatus
from schemes.dto.embedding import EmbeddingResult, SparseVector
from schemes.events import TOPIC_CHUNKS_EMBED, ChunkEmbeddedEvent, DocumentParsedEvent
from services.ingestion.embed_ingest_service import EmbedIngestService

MODEL = "BAAI/bge-m3"


def _make_service() -> tuple[EmbedIngestService, AsyncMock, AsyncMock, AsyncMock]:
    embedding_service = AsyncMock()
    status_repo = AsyncMock()
    kafka_producer = AsyncMock()
    service = EmbedIngestService(
        embedding_service=embedding_service,
        document_status_repository=status_repo,
        kafka_producer=kafka_producer,
    )
    return service, embedding_service, status_repo, kafka_producer


def _parsed_event(chunk_index: int = 0, with_sparse: bool = True) -> DocumentParsedEvent:
    return DocumentParsedEvent(
        document_id="doc1",
        collection_name="docs",
        filename="a.txt",
        chunk_id="c1",
        chunk_index=chunk_index,
        text="hello",
        total_chunks=2,
        embedding_model=MODEL,
        dense_vector_name="dense",
        sparse_vector_name="sparse" if with_sparse else None,
        with_sparse=with_sparse,
    )


def test_handle_success_with_sparse_publishes_embedded():
    # 청크를 임베딩해 dense+sparse와 소비 토큰을 담은 chunks.embed를 발행한다.
    service, embedding_service, status_repo, kafka_producer = _make_service()
    embedding_service.embed_documents.return_value = (
        [EmbeddingResult(dense=[1.0, 2.0, 3.0], sparse=SparseVector([1], [0.5]))],
        7,
    )

    asyncio.run(service.handle(AsyncMock(), _parsed_event(chunk_index=0)))

    # 첫 청크(chunk_index=0)면 상태를 EMBEDDING으로 전환한다.
    status_repo.set_status.assert_awaited_once()
    assert status_repo.set_status.await_args.args[2] == DocumentStatus.EMBEDDING

    kafka_producer.publish.assert_awaited_once()
    assert kafka_producer.publish.await_args.args[0] == TOPIC_CHUNKS_EMBED
    embedded = ChunkEmbeddedEvent.from_bytes(
        kafka_producer.publish.await_args.kwargs["value"]
    )
    assert embedded.dense == [1.0, 2.0, 3.0]
    assert embedded.sparse_indices == [1]
    assert embedded.sparse_values == [0.5]
    assert embedded.embedding_model == MODEL  # 비용 집계용 모델명 전달.
    assert embedded.embedding_tokens == 7  # 소비 토큰을 이벤트로 흘려보낸다.
    assert embedded.created_at  # 적재 payload용 생성 시각이 채워진다.


def test_handle_success_without_sparse_omits_sparse_fields():
    # with_sparse=False면 sparse 필드를 비운 채 발행하고 상태 전환은 첫 청크만.
    service, embedding_service, status_repo, kafka_producer = _make_service()
    embedding_service.embed_documents.return_value = (
        [EmbeddingResult(dense=[1.0, 2.0, 3.0], sparse=None)],
        None,
    )

    asyncio.run(
        service.handle(AsyncMock(), _parsed_event(chunk_index=1, with_sparse=False))
    )

    # 두 번째 청크(chunk_index=1)이므로 상태 전환은 하지 않는다.
    status_repo.set_status.assert_not_awaited()
    embedded = ChunkEmbeddedEvent.from_bytes(
        kafka_producer.publish.await_args.kwargs["value"]
    )
    assert embedded.sparse_indices is None
    assert embedded.sparse_values is None
