"""모델 단가 기본값(시딩용).

100만(1M) 토큰당 USD 기준. 런타임에 model_pricing 테이블에서 수정 가능하며,
여기 값은 시작 시 upsert되는 기본값이다.

- 임베딩: 로컬(fastembed) 모델은 0, OpenAI text-embedding-3-* 는 공개 단가.
- 채팅: core/model_config/chat_model_config.py 카탈로그의 모델명과 동일한
  키로 등록해야 UsageStatsService가 비용을 계산한다(다르면 cost=None).
"""

# 로그에는 컬렉션 생성 시 고른 카탈로그 키가 저장되므로, 단가도 같은 키로 등록.
# (fastembed 로컬 모델은 카탈로그 키가 "BAAI/bge-m3")
_FASTEMBED_LOCAL = "BAAI/bge-m3"

default_pricing_rows: list[dict[str, object]] = [
    # --- Embedding (input만 과금, output=0) ---
    {
        "model": _FASTEMBED_LOCAL,
        "kind": "embedding",
        "input_price_per_1m": 0.0,
        "output_price_per_1m": 0.0,
        "currency": "USD",
    },
    {
        "model": "text-embedding-3-small",
        "kind": "embedding",
        "input_price_per_1m": 0.02,
        "output_price_per_1m": 0.0,
        "currency": "USD",
    },
    {
        "model": "text-embedding-3-large",
        "kind": "embedding",
        "input_price_per_1m": 0.13,
        "output_price_per_1m": 0.0,
        "currency": "USD",
    },
    # --- Chat (input/output 모두 과금) ---
    {
        "model": "gpt-4o-mini",
        "kind": "chat",
        "input_price_per_1m": 0.15,
        "output_price_per_1m": 0.60,
        "currency": "USD",
    },
    {
        "model": "gpt-4o",
        "kind": "chat",
        "input_price_per_1m": 2.50,
        "output_price_per_1m": 10.00,
        "currency": "USD",
    },
]
