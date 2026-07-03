"""Kafka 토픽 이름 상수 (단계 경계 = 토픽)."""

# 업로드 직후: endpoint → Parser Worker
TOPIC_DOCUMENTS_UPLOADED = "documents.uploaded"
# 청킹 결과(청크당 1메시지): Parser Worker → Embed Worker
TOPIC_DOCUMENTS_PARSED = "documents.parsed"
# 임베딩 결과: Embed Worker → Index Worker
TOPIC_CHUNKS_EMBED = "chunks.embed"
# 실패 격리(dead-letter): 모든 워커 → 운영/재처리 도구
TOPIC_DOCUMENTS_DLQ = "documents.dlq"

# API·워커 시작 시 ensure_topics로 생성할 토픽 목록.
ALL_TOPICS = [
    TOPIC_DOCUMENTS_UPLOADED,
    TOPIC_DOCUMENTS_PARSED,
    TOPIC_CHUNKS_EMBED,
    TOPIC_DOCUMENTS_DLQ,
]
