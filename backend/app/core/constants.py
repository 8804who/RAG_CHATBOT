# 문서 청킹 기본값(utils/chunker.py)
DEFAULT_CHUNK_SIZE = 400  # 청크당 최대 단어 수
DEFAULT_CHUNK_OVERLAP = 80  # 인접 청크 간 겹칠 단어 수

# 문서 관리 로그 처리 상태(DocumentManageLog.status)
DOCUMENT_LOG_STATUS_SUCCESS = "success"
DOCUMENT_LOG_STATUS_FAILED = "failed"

# 사용량 집계 기본 통화(ModelPricing.currency 기본값)
DEFAULT_CURRENCY = "USD"

# 하이브리드 검색 기본 top-k(RetrievalService)
DEFAULT_RETRIEVAL_TOP_K = 8

# 채팅 생성 응답의 서버 강제 상한 토큰 수(프론트 값 불신, 비용/DoS 방어)
DEFAULT_CHAT_MAX_COMPLETION_TOKENS = 1024
