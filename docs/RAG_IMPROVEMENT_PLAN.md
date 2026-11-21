# RAG 개선 계획 (T-028)

작성 2026-11-21 · 작성 `rag-researcher` · 갱신 2026-11-21(v2 평가 하네스와 v2 기준선 반영, T-029~T-031) · 상태: 평가 하네스 v2 완료, 운영 코드는 아직 바꾸지 않았다.

이 문서는 검색기(retriever), 임베딩, 챗봇 답변 품질을 **한 번에 하나씩 바꾸고, 같은 시나리오로 다시 재서 "지표 A → B, 비용 +X"로 보고**하기 위한 계획이다. 숫자의 출처는 세 가지이고, 모든 숫자에 출처를 붙였다.

- **[측정]** T-027 베이스라인 E2E 평가(`eval/results/2026-11-21-baseline-r1|r2`, 옛 9건 세트)와 T-031 v2 기준선(`eval/results/2026-11-21-baseline-v2`, 110건). **앞으로 비교 기준은 v2다.**
- **[프로브]** 이번 작업(T-028)에서 돌린 오프라인 검색 프로브. LLM 호출 없이 Qdrant에 저장된 벡터로 운영 검색을 재현했다(부록 A).
- **[추정]** 문헌이나 경험에 기댄 예상치. 측정값이 아니다.

---

## 0. 요약

**v2 기준선 (2026-11-21, 1회): 110건 중 36건 통과.** 평가 하네스를 고친 뒤(§3.1) 다시 잰 결과, 가장 큰 문제는 검색기가 아니라 **에이전트가 문서를 검색하지 않는 것**이다. RAG 60건 중 `search_documents`를 부른 건 24건뿐이고 나머지는 `tavily_search`(웹)로 가서 2022년 정보 같은 낡은 답을 냈다(P20). 문서를 찾은 경우에도 300자 snippet에 답이 없으면 틀린다(P15, 예: `ko-rag-election-result`는 recall 1, correctness 0). 그래서 다음 순서는 **A1(검색 강제) → A3(고정 컬렉션에서 웹 도구 제거) → A2(전체 청크 전달)**이다. 아래 1~4는 옛 9건 세트에서 찾은 문제이고, 1번은 v2 하네스로 해결됐다.

1. **(해결: v2 하네스) 지금 평가로는 품질 변화를 측정할 수 없다.** golden `expectedDocumentIds`가 재인제스트 이후 낡아서 precision이 모두 0이다. 9개 케이스 중 4개는 도구를 아예 부르지 않고 모델 기억으로 답한다. 그런데도 judge는 평균 0.91을 준다. judge가 답만 정답과 비교하고 근거는 보지 않기 때문이다. 9건이면 케이스 하나가 11%p이므로 웬만한 개선은 노이즈에 묻힌다.
2. **Dense 임베딩이 청크 텍스트의 약 1/4을 보지 못한다.** e5-large는 512토큰에서 잘리는데, 400단어 청크는 e5 토큰으로 중앙값 669개다. 69개 청크 중 67개가 잘리고, 청크당 평균 24.5%가 임베딩에 반영되지 않는다 [프로브].
3. **한국어 질의에서는 BM25가 hybrid를 망친다.** 한국어로 번역한 같은 9문항에서 Hit@3이 dense 단독 0.889, hybrid 0.556이었다 [프로브]. 로드맵의 한국어 세트로 가기 전에 꼭 알아야 할 점이다.
4. **에이전트는 검색 결과를 300자만 본다.** 정답 숫자가 잘린 snippet 뒤에 있으면 같은 검색을 반복한다(최대 5회, 입력 28.8k 토큰). 정답이 보이는 snippet을 받은 경우는 회차마다 9건 중 2건뿐이었다 [측정+프로브]. 나머지 정답은 대부분 기억에서 나왔다.

먼저 할 일은 **평가를 고치는 것**이다(§3.1). 그 다음에는 **근거를 실제로 보고 답하게 만들고**(A1/A2), 그 뒤에 **청크를 512토큰 안에 맞춘다**(M1). 프로브에서 가장 큰 검색 개선은 M1이었다(청크 크기만 바꿨을 때 MRR@8 0.667 → 0.815, n=9라서 방향만 참고).

---

## 1. 베이스라인

### 1.1 v2 기준선 (T-031, 2026-11-21) — 앞으로의 비교 기준

결과 파일: [`baseline-v2.md`](../eval/results/2026-11-21-baseline-v2.md) / [`.json`](../eval/results/2026-11-21-baseline-v2.json)

설정: 채팅 `gpt-4o-mini`, judge `gpt-6.2-sol`(검색된 300자 snippet을 함께 보고 correctness와 groundedness를 따로 채점), `intfloat/multilingual-e5-large` 1024d, dense+BM25 RRF, top_k=8, 400단어/80 중첩, 컬렉션 `rag_eval_v2`(문서 10개, 15청크: 2025·2026 발롱도르, 2026 월드컵, 2025 콘클라베, 2026 동계올림픽, 2025 대선, APEC 2025 경주, KBO 2025, 2026 지방선거, 2025 영남 산불) + `rag_eval_papers`. 1회 실행이라 회차 간 분산은 아직 모른다.

| 지표 | ko-rag | en-rag | ko-nonrag | en-nonrag | tool | 전체 |
|---|---|---|---|---|---|---|
| 케이스 | 30 | 30 | 15 | 15 | 20 | 110 |
| pass | 2 | 4 | 11 | 10 | 9 | **36** |
| recall | 0.400 | 0.367 | - | - | 1.000 | 0.456 |
| precision | 0.142 | 0.161 | - | - | 0.232 | 0.161 |
| correctness | 0.498 | 0.822 | 0.740 | 0.750 | 0.626 | 0.677 |
| groundedness | 0.573 | 0.618 | 0.491 | 0.566 | 0.661 | 0.589 |
| 행동(도구 규칙) 통과율 | 0.433 | 0.333 | 0.733 | 0.733 | 0.850 | 0.564 |
| 평균 입력 / 출력 토큰 | 8240 / 196 | 6382 / 165 | 4398 / 85 | 3129 / 74 | 6097 / 154 | 6123 / 148 |
| 평균 도구 호출 | 1.57 | 1.47 | 0.60 | 0.47 | 1.45 | 1.24 |
| latency p50 / p95 (ms) | 6887 / 13052 | 5783 / 10895 | 3531 / 9876 | 2980 / 7250 | 4334 / 9707 | 5518 / 10895 |

### 1.2 옛 9건 세트 (T-027, 2026-11-21) — 기록용, v2와 비교하지 않는다

결과 파일: [`baseline-r1.md`](../eval/results/2026-11-21-baseline-r1.md) / [`.json`](../eval/results/2026-11-21-baseline-r1.json), [`baseline-r2.md`](../eval/results/2026-11-21-baseline-r2.md) / [`.json`](../eval/results/2026-11-21-baseline-r2.json)

설정: `gpt-4o-mini`(채팅과 judge 모두), `intfloat/multilingual-e5-large` 1024d, dense+BM25 RRF, top_k=8, 400단어 윈도우/80 중첩, 컬렉션 `rag_eval_papers`(Transformer 19, BERT 31, GPT 19 청크), 9케이스.

| 지표 | r1 | r2 | 비고 |
|---|---|---|---|
| pass | 0/9 | 0/9 | stale id 때문에 precision 게이트에서 전부 실패 |
| precision (채점값) | 0 | 0 | golden id가 현재 컬렉션에 없음 |
| precision (현재 id로 재계산) | 0.259 | 0.222 | 도구 호출이 없는 케이스는 0으로 계산 |
| judge 평균 | 0.911 | 0.944 | 같은 설정에서 회차 간 차이 0.033 |
| 평균 입력 / 출력 토큰 | 8168 / 176 | 7905 / 177 | |
| 평균 도구 호출 | 1.556 | 1.556 | 도구 0회 케이스 4/9 |
| latency p50 / p95 | 5.7 s / 10.8 s | 6.3 s / 11.2 s | LLM이 95% 이상, 임베딩 ~69 ms, Qdrant ~13 ms |

[프로브] 운영 검색을 그대로 재현한 결과(golden 질의 원문, LLM 질의 재작성 없음): 문서 precision@8 0.667, 정답 청크 hit@8 0.778, MRR@8 0.667, GPT 케이스의 문서 precision@8 0.208.

---

## 2. 발견한 문제

실패 유형은 retrieval miss, ranking miss, context miss, generation miss, routing miss, dataset issue로 나눴다.

### 평가 하네스

P1~P6은 v2 하네스(PR #7, T-030/T-031)로 해결했거나 대부분 해결했다. 상태 열에 남은 일을 적었다.

| # | 문제 | 유형 | 근거 | 상태 (2026-11-21) |
|---|---|---|---|---|
| P1 | golden `expectedDocumentIds`가 낡았다(2026-11-14 재인제스트) | dataset | precision 0/9, baseline-r1.md post-hoc notes. 현재 id: Transformer `335fdb77…`, BERT `9d4573d1…`, GPT `adc3e49f…` | **해결.** v2 fixture는 `expectedDocumentTitles`(파일명)로 라벨링하고, 실행할 때 `document_progress_status`(INDEXED)에서 id로 해석한다. 해석이 안 되면 케이스 실패. 재인제스트해도 깨지지 않는다 |
| P2 | judge가 정답 일치만 보고 근거 충실성은 보지 않는다. 기억으로 쓴 답도 만점을 받는다 | eval | `eval/src/judge.ts:5-10,64`: 질문, 정답, 답변만 넘기고 검색 컨텍스트는 넘기지 않는다. 도구 0회인 4케이스가 0.8~1.0을 받았다 | **해결.** judge가 검색된 청크를 함께 보고 correctness와 groundedness를 따로 채점한다(v2 전체 0.677 / 0.589). 남은 한계: judge가 보는 건 300자 snippet이다(P15) |
| P3 | 답에 쓰인 근거가 실제로 보였는지 측정하지 않는다 | eval | [프로브] 인용 snippet(=에이전트가 본 300자) 안에 정답 사실이 있는 경우: r1 2/9, r2 2/9(bert-masking, gpt-ablation). judge 평균은 0.91/0.94 | **대부분 해결.** groundedness 점수와 케이스별 도구 호출 순서, 검색된 doc/chunk id를 기록한다. 별도의 answer-in-context 비율 지표는 아직 없다 |
| P4 | judge 모델이 채팅 모델과 같다(`gpt-4o-mini`) | eval | 자기 선호 편향 위험(Panickssery et al., 2024, *LLM Evaluators Recognize and Favor Their Own Generations*, 중간 강도의 근거) | **해결.** judge 기본값을 상위 모델 `gpt-6.2-sol`로 바꿨다(`JUDGE_MODEL`로 변경 가능). 남은 일: 같은 벤더라 다른 계열 judge와 사람 채점 20건으로 일치도 확인, seed 고정 |
| P5 | 9건, 영어만, 케이스당 문서 1개, 청크 라벨 없음. 답 없음, 다문서, 한국어 케이스도 없다 | eval | `eval/fixtures/golden-dataset.json`. 케이스 하나가 11.1%p이고 회차 간 judge 차이가 0.033이다. 유명 논문이라 모델이 이미 외우고 있다(Mallen et al., 2023, *When Not to Trust Language Models*: 인기 있는 지식일수록 파라메트릭 기억이 강하다) | **대부분 해결.** v2 110건: ko-rag 30, en-rag 30, ko-nonrag 15, en-nonrag 15, tool 20. 모델이 모르는 2025~2026년 사실 문서 10개(`rag_eval_v2`, 출처 URL 포함), 문서 밖 질문(not_in_docs), 다문서 케이스 4건. 남은 일: 청크 단위 라벨, dev/test 분리, ~150건 목표, 대부분 사실이 출처 1개로만 확인됨 |
| P6 | `eval/README.md`의 청크 수가 낡았다(7/5/5라고 적혀 있지만 실제는 19/31/19). 그 숫자로 정한 precision 상한 설명(0.5)도 더는 맞지 않는다 | doc | `eval/README.md` "Precision ceiling" 문단. 문서 담당자가 고쳐야 한다 | **해결.** README에 19/31/19와 v2 컬렉션의 precision 상한(~1/7, P23)을 적었다 |

### 검색기

| # | 문제 | 유형 | 근거 |
|---|---|---|---|
| P7 | **GPT 논문 본문에는 "GPT"라는 단어가 0번 나온다.** BERT 논문에는 "OpenAI GPT"가 15개 청크에 36번 나온다. 청크에는 문서 제목도 붙지 않는다 | retrieval/ranking | [프로브] 문자열 카운트. GPT 케이스 문서 precision@8은 0.208(hybrid)과 0.083(BM25 단독)이다. "BooksCorpus"와 "768"도 BERT 청크에 나온다(hard negative) |
| P8 | Hybrid가 dense 단독보다 낫지 않다. BM25가 GPT 케이스를 망친다 | ranking | [프로브] 문서 P@8: dense 0.722, hybrid 0.667, BM25 0.625 |
| P9 | RRF k=2(Qdrant 기본값)이다. 원 논문은 k=60이다. prefetch 깊이도 최종 top_k와 같은 8이다 | ranking | `qdrant_repository.py:308,314,317`, Qdrant `DEFAULT_RRF_K = 2`(Context7, qdrant/qdrant). Cormack et al., 2009, *Reciprocal Rank Fusion outperforms Condorcet…*. [프로브] prefetch 50으로 늘려도 개선 없음(0.653) |
| P10 | BM25 인코더 `Qdrant/bm25`는 영어 Snowball stemmer를 쓰고 한국어를 지원하지 않는다 | retrieval (한국어) | `fastembed/sparse/bm25.py:25-52,98`(language 기본값 `"english"`, 지원 언어 목록에 korean 없음), `bm25_sparse_encoder.py:14`. [프로브] 한국어 질의의 BM25 단독 Hit@8은 0.222이고, hybrid에 섞이면 Hit@3이 0.889에서 0.556으로 떨어진다 |
| P11 | top_k=8 고정, reranker 없음, 점수 컷오프 없음. 점수로는 정답과 오답이 갈리지 않는다 | ranking | `constants.py:13`. 엔지니어 측정: dense 중앙값 hit 0.832 vs miss 0.835, RRF 0.338 vs 0.273. 그래서 점수 컷오프(KI-004)만으로는 효과가 없다 |

### 임베딩과 청킹

| # | 문제 | 유형 | 근거 |
|---|---|---|---|
| P12 | **512토큰 절단.** 청커가 토큰이 아니라 단어를 센다 | retrieval | `utils/chunker.py:25`(`text.split()`), `constants.py:2-3`, fastembed `common/preprocessor_utils.py:52`(`enable_truncation(max_length=512)`). [프로브] e5 토크나이저 기준 청크 중앙값 669토큰(최소 347, 최대 880), 512 초과 67/69, 청크당 평균 24.5%가 잘림 |
| P13 | e5의 `query: ` / `passage: ` 접두사를 쓰지 않는다 | retrieval | fastembed 모델 설명 "Prefixes for queries/documents: necessary"(`text/pooled_embedding.py:77-78`). 그런데 기본 `query_embed`는 접두사 없이 `embed`를 호출한다(`text/text_embedding_base.py:56-60`). 우리 클라이언트도 원문을 그대로 넘긴다(`fastembed_embedding_client.py:33,38`). Wang et al., 2024, *Multilingual E5 Text Embeddings: A Technical Report*. [프로브] 이 데이터셋에서는 효과가 작다(MRR 0.667 → 0.722) |
| P14 | pdftotext 잡음: 첫 청크에 arXiv 헤더와 저자 이메일, 수식 기호 깨짐(⟨s⟩ → `hsi`) | context | [프로브] 청크 원문 확인. 단일 문자 토큰 비율 4.5%. 우선순위는 낮다 |

### 챗봇과 에이전트

| # | 문제 | 유형 | 근거 |
|---|---|---|---|
| P15 | 에이전트가 청크를 300자 snippet으로만 본다 | context | `tools.py:23,34`. 인용 snippet도 같은 값이다(`agent_orchestrator.py:287`). 예: transformer-bleu-score에서 snippet이 "...by more than 2.0 "에서 끊겨 "28.4"가 보이지 않는다. 그래서 검색을 5번 하고 입력 28,804토큰을 쓴다(r1). 그래도 답은 28.4로 맞게 나왔는데, 기억에서 나온 것이다 |
| P16 | 도구 출력의 약 55%가 메타데이터다(`chunk_id`, `document_id`, `collection_name`) | 비용 | `tools.py:30-36`, 엔지니어 측정 |
| P17 | 프롬프트가 검색 없이 답하는 것을 허용한다("필요한 도구를 스스로 선택") | generation | `constants.py:38-46`. 도구 0회 4/9 |
| P18 | 컬렉션이 고정된 채팅에도 tavily, arXiv 도구 스키마가 붙는다. 웹 결과가 인용에 섞인다 | 비용/routing | `agent_orchestrator.py:153-164`. gpt-pretraining-corpus가 web 인용 5건(r1) |
| P20 | **[v2] 에이전트가 문서 대신 웹으로 간다.** RAG 60건 중 `search_documents` 호출 24건, 나머지는 `tavily_search`. 웹 결과로 2022년 같은 낡은 사실을 답한다 | routing | baseline-v2: ko-rag 행동 통과율 0.433, en-rag 0.333. 예: `ko-rag-election-turnout`, `ko-rag-apec-venue` "expected tool search_documents was not called" |
| P21 | **[v2] 금지된 웹 검색과 과다 호출.** nonrag 8건이 금지된 `tavily_search`를 불렀고, 3건이 `maxToolCalls`를 넘었다 | routing/비용 | baseline-v2 Cases 표의 behavior 열 |
| P22 | **[v2] 검색 후 계산에서 인자가 틀린다.** search-then-calc 2건이 `calculate`에 자리표시 변수나 틀린 숫자를 넘겼다 | generation | baseline-v2 tool 세트. P15(300자 snippet)로 숫자가 안 보이는 것과 관련 있을 가능성 [추정] |
| P23 | **[v2] 작은 컬렉션 때문에 precision 상한이 낮다.** `rag_eval_v2`는 10문서 15청크라 top-8이 약 7개 문서를 가져온다. 단일 문서 질문의 precision이 ~1/7로 묶여 `MIN_PRECISION=0.3`을 넘을 수 없다. RAG 7건이 precision만으로 실패했다 | eval | baseline-v2. 결정 필요: v2 케이스의 임계값을 낮추거나, 문서를 늘린다(기준선이 바뀐다) |
| P19 | 한 턴 안에서는 ReAct 루프가 이전 도구 결과를 매 호출마다 다시 보낸다. 반대로 이전 대화 이력은 에이전트에 전혀 넘어가지 않는다 | 비용/기능 | `agent_orchestrator.py:182-183`(`messages`에 현재 query만 넣는다). 멀티턴 후속 질문은 동작하지 않는다. 품질 평가 범위 밖이지만 기록해 둔다 |

---

## 3. 개선안 (순위순)

"예상 효과"는 특별히 표시하지 않으면 **[추정]**이다. 비용 열의 "LLM 호출"은 턴당 LLM 호출 수에 주는 영향이다.

### 3.1 평가 하네스 (먼저)

**진행 상황 (T-030/T-031, 2026-11-21).** E1 완료: fixture는 `filename`으로 라벨링하고, 실행할 때 `document_progress_status`(INDEXED)에서 id로 해석한다. 해석이 안 되면 0점이 아니라 케이스 실패로 처리한다. E3 일부 완료: judge가 correctness와 groundedness를 따로 매기고, 도구 호출 순서를 전부 기록한다. 단, judge가 보는 건 에이전트가 본 청크의 앞 300자이고 도구 출력 전문은 아니다. E4 완료: judge 기본값을 `gpt-6.2-sol`로 바꿨다(seed 고정은 아직). E5는 첫 단계만 했다. v2 세트 110건(ko-rag 30, en-rag 30, ko-nonrag 15, en-nonrag 15, tool 20)과 새 문서 10개(`rag_eval_v2`, `npm run ingest:v2`)를 만들었고, dev/test 분리는 아직 안 했다. E2와 E6은 아직이다. 기준선은 `eval/results/2026-11-21-baseline-v2`(1회)다.

**v2 기준선에서 드러난 점.** `rag_eval_v2`는 문서 10개가 15청크라서, top-8로 단일 문서 질문을 하면 문서 단위 precision이 구조적으로 0.3을 넘을 수 없다(`MIN_PRECISION=0.3`). RAG 케이스 중 7건은 precision만으로 실패했다. 임계값을 바꿀지, 문서를 늘릴지는 따로 결정해야 한다. 또 RAG 60건 중 `search_documents`를 부른 건 24건뿐이었고, 나머지는 `tavily_search`로 갔다. 이건 하네스 문제가 아니라 에이전트 쪽 문제다(3.4).

| 순위 | 변경 | 기대 효과 | 노력 | 위험 | 측정 지표 |
|---|---|---|---|---|---|
| E1 | golden id를 현재 id로 다시 매핑한다. 앞으로는 id 대신 `filename`(또는 문서 해시)으로 라벨링하고 실행할 때 id를 해석한다 | precision 0 → ~0.26 [측정: 재계산값]. pass/fail이 의미를 갖게 된다 | S (반나절) | 없음 | `meanPrecision`, `passCount` |
| E2 | **오프라인 검색 평가 스크립트**(LLM 없음). 청크 라벨은 chunk id가 아니라 **근거 문자열(evidence span)**로 달고, 실행할 때 청크에 매핑한다. 이렇게 해야 청크 크기를 바꾸는 실험에서도 라벨이 유지된다 | 검색 변경을 몇 초 만에, 무료로, 결정적으로 비교할 수 있다. E2E에서 생기는 LLM 노이즈가 없다 | S-M (1~2일). 부록 A의 프로브 스크립트를 출발점으로 쓴다 | 정규식 라벨은 거짓 양성이 생길 수 있다. 사람이 검수해야 한다 | Recall@k, MRR@k, nDCG@k, Hit@k(k=3,5,8) |
| E3 | **근거성(groundedness) 지표.** 에이전트가 실제로 본 텍스트(도구 출력)를 judge에 함께 넘겨서 답의 주장이 컨텍스트에 있는지 채점한다. 함께 기록할 것: `toolCalled` 비율, "답에 쓰인 사실이 보인 컨텍스트에 있는가" 비율 | 지금 0.91인 judge가 기억으로 답한 경우를 가려낸다. 실제 근거성은 [측정] 기준 2/9 수준으로 보인다 | M (2일) | judge 프롬프트가 바뀌므로 이전 judge 점수와 직접 비교할 수 없다. 그래서 새 지표로 따로 둔다 | faithfulness(0-1), tool-call rate, answer-in-context rate |
| E4 | judge를 다른 모델 계열이나 상위 모델로 바꾼다(예: `gpt-4o` 또는 다른 벤더). 고정 seed와 temperature 0 | 자기 선호 편향 제거(P4) | S | judge 비용 증가(케이스당 1콜, 모델 단가만큼) | judge 일치도. 20건 정도를 사람이 채점해 대조한다 |
| E5 | **데이터셋 확대.** 로드맵의 한국어 golden ~150건으로 간다. 구성: 단일 사실, 다문서 비교, **답 없음(거절 기대)**, hard negative(BERT vs GPT), 한국어 질의 × 영어 문서, 덜 유명한 문서(기억 교란 제거) | 개선을 통계적으로 구분할 수 있게 된다. n=150이면 케이스 하나가 0.67%p | L (1~2주, 라벨링이 대부분) | 튜닝용과 테스트용 분리가 필수다(dev 30% / test 70%, 튜닝은 dev에서만) | 위 지표 전부와 refusal accuracy |
| E6 | **반복과 신뢰구간.** E2E는 변형마다 3회 이상 돌린다. paired bootstrap 95% CI로 비교한다 | 회차 간 차이(judge 0.033, p50 0.6 s)를 개선으로 착각하지 않게 된다 | S | 실행 비용이 3배 | Δ 지표의 95% CI |

### 3.2 검색기 (Retriever)

| 순위 | 변경 | 근거 | 기대 효과 | 노력 | 위험/비용 | 측정 지표 |
|---|---|---|---|---|---|---|
| R1 | **문맥 청크 헤더.** 인제스트 때 각 청크 앞에 `문서 제목 + (가능하면) 섹션명`을 붙여 dense와 sparse 양쪽에 반영한다. 다음 단계로 LLM이 쓴 1~2문장 문맥을 붙이는 Contextual Retrieval이 있다 | P7. Anthropic, 2024, *Introducing Contextual Retrieval*(블로그, 동료 심사 없음): top-20 검색 실패가 contextual embedding으로 -35%, BM25까지 쓰면 -49%, rerank까지 더하면 -67%라고 보고 | [프로브] 제목만 붙였을 때 GPT 케이스 문서 P@8이 0.208 → 0.333(hybrid), dense 단독 0.500. 전체 MRR은 그대로 | S (제목만) / M (LLM 문맥) | 제목만 붙이면 비용 0. LLM 문맥은 **인제스트 때 청크마다 LLM 1콜**(쿼리 시점 비용은 없음) | 문서 P@k, MRR, GPT 계열 hard negative 케이스 |
| R2 | **Cross-encoder reranker.** hybrid로 top 30~50을 뽑고 rerank해서 최종 k=5로 줄인다. 다국어 후보: `jinaai/jina-reranker-v2-base-multilingual`(fastembed 0.8에 내장, `rerank/cross_encoder/onnx_text_cross_encoder.py:58`), `BAAI/bge-reranker-v2-m3` | Nogueira & Cho, 2019, *Passage Re-ranking with BERT*(강한 근거, 다수 재현). P11: 1단계 점수로는 정답과 오답이 갈리지 않는다 | nDCG@5 +5~15pt [추정]. reranker 점수는 컷오프 기준으로 쓸 수 있을 만큼 분리될 가능성이 높다(그래야 KI-004 해결) | M | CPU에서 쿼리당 +100~500 ms [추정, 반드시 측정]. LLM 호출 증가 없음. 최종 k를 줄이면 입력 토큰이 감소 | nDCG@5, MRR, 최종 k별 Recall, rerank latency |
| R3 | **융합 튜닝.** dense 단독, RRF k=2/60, 가중 RRF(dense 가중↑), prefetch 깊이를 비교한다 | P8, P9. Qdrant `Rrf(k, weights)` 지원(Context7) | [프로브] 이 9건에서는 dense 단독이 hybrid를 이겼다(영어 MRR 0.736 vs 0.667, 한국어 질의 Hit@3 0.889 vs 0.556). 한국어 문서와 고유명사가 많은 세트에서는 결과가 다를 수 있으니 **결정은 E5 세트로 내린다**. 그 전까지는 한국어 질의에 BM25 가중을 낮추는 것이 안전한 기본값이다 | S | 없음 | Recall@8, MRR |
| R4 | **한국어 BM25 토큰화**(Kiwi 형태소). 한국어 문서가 들어온 뒤에 진행한다 | P10. 공백 단위 토큰화는 조사가 붙은 어절("Transformer는")을 하나의 토큰으로 본다 | 한국어 질의 × 한국어 문서에서 BM25 recall 상승 [추정]. 한국어 질의 × 영어 문서에서는 효과 없음 | M (커스텀 sparse 인코더 + 재인제스트) | 형태소 분석 지연은 수 ms | BM25 단독 Recall@k, hybrid MRR (한국어 세트) |
| R5 | 동적 k와 점수 컷오프. **R2 이후에만** 의미가 있다 | P11 | 답 없음 질문의 거절 정확도 상승, 입력 토큰 감소 [추정] | S | recall 손실 위험 | refusal accuracy, Recall@k |

### 3.3 임베딩과 청킹

| 순위 | 변경 | 근거 | 기대 효과 | 노력 | 위험/비용 | 측정 지표 |
|---|---|---|---|---|---|---|
| M1 | **토큰 기준 청킹.** 고정된 임베딩 모델의 토크나이저로 세어서 청크를 512토큰 이하로 만든다. 로드맵의 256/512/1024 토큰 비교에서 e5는 1024가 불가능하다(512에서 잘림). 1024는 긴 컨텍스트 모델(bge-m3, OpenAI 3-small/large)에서만 비교한다 | P12. 잘린 부분은 dense 검색에서 안 보이고 BM25에서만 보인다 | [프로브] 청크 크기만 바꿨을 때(V4 → V5, 400단어 → 300단어 ≈ 512토큰 이하) MRR@8 0.667 → 0.815, Hit@3 0.778 → 0.889, Recall@8 0.694 → 0.833, 문서 P@8 0.708 → 0.792. 150단어는 MRR 0.722로 300단어보다 낮다(사실이 쪼개진다) | S-M (청커 + 재인제스트) | 청크 수가 1.3~2.7배로 늘어난다. Qdrant 용량은 무시할 수준 | Recall@k, MRR, nDCG, 컨텍스트 토큰 |
| M2 | **e5 접두사** `query: ` / `passage: ` | P13. 모델 카드 필수 사항 | [프로브] MRR 0.667 → 0.722, 다른 지표는 그대로. 효과는 작지만 비용이 0이고 모델 사양을 맞추는 일이다 | S (재인제스트 필요. 쿼리와 문서를 반드시 같이 바꿔야 한다) | 접두사가 섞인 컬렉션은 검색이 깨진다. 컬렉션 단위로 버전을 관리한다 | MRR, Recall@k |
| M3 | **임베딩 모델 비교**(한국어 세트에서). e5-large(현행), `BAAI/bge-m3`(dense+sparse, 8192토큰, Chen et al., 2024, *BGE M3-Embedding*), OpenAI `text-embedding-3-small/large`(이미 카탈로그에 있음, `embedding_model_config.py`). 차원을 줄여 비용을 낮추려면 Matryoshka 절단(OpenAI 3계열 `dimensions`)도 본다 | 컬렉션별 모델 고정 구조(`core/model_config/`) 덕분에 변형마다 컬렉션 하나씩 만들어 A/B할 수 있다 | 미정. 이 코퍼스에서는 측정해 봐야 안다 | M | OpenAI는 임베딩 API 비용과 쿼리당 네트워크 왕복(+수십~수백 ms) | Recall@k, MRR, 쿼리 latency, $/1k 쿼리 |
| M4 | PDF 정제. arXiv 헤더, 이메일, 페이지 번호를 제거한다 | P14 | 작다 [추정] | S | 없음 | Recall@k |

### 3.4 챗봇과 에이전트

| 순위 | 변경 | 근거 | 기대 효과 | 노력 | 위험/비용 | 측정 지표 |
|---|---|---|---|---|---|---|
| A1 | **(v2 기준 최우선, P20)** **검색 강제와 거절 규칙.** 고정 컬렉션 채팅에서는 첫 턴에 `search_documents` 호출을 강제한다(`tool_choice` 또는 프롬프트). 프롬프트에는 "검색 결과에 없는 사실은 쓰지 말고, 없으면 모른다고 답하라"를 넣는다 | P2, P17 | tool-call rate 5/9 → 9/9 [추정]. faithfulness 상승. 기억 교란이 제거되어 **검색기 개선이 답변 지표에 드러나기 시작한다**. judge 점수는 오히려 떨어질 수 있다(정직한 거절) | S | 도구 0회 케이스에 LLM 호출이 1회 늘어난다(+~1.5k 입력 토큰, +1~2 s [추정]) | faithfulness, tool-call rate, refusal accuracy, judge |
| A2 | **도구 출력을 전체 청크 텍스트로 바꾸고 메타데이터는 줄인다.** LLM에는 `[n] 파일명 · 청크텍스트`만 주고, id 매핑은 서버가 보관한다 | P15, P16 | 반복 검색이 줄어 평균 도구 호출 1.56 → ~1.1 [추정]. 입력 토큰은 호출당 늘지만 호출 수가 줄어 상쇄되거나 감소(bleu 케이스 28.8k가 기준). answer-in-context 2/9 → 대부분 | S | 1회 검색 컨텍스트가 8청크 × ~500토큰 = ~4k 토큰. R2로 최종 k를 줄이면 상쇄된다 | meanToolCalls, meanInputTokens, answer-in-context, faithfulness |
| A3 | 고정 컬렉션 채팅에서는 웹/arXiv 도구를 빼거나 옵트인으로 바꾼다. 라우팅 채팅에서는 "문서 먼저, 문서에 없을 때만 웹" 규칙을 프롬프트에 넣는다 | P18, P20, P21 | 스키마 토큰 절감, 문서 밖 웹 인용 0 | S | 사용자가 웹 검색을 원할 때 기능이 줄어든다(UI 토글로 해결) | meanInputTokens, web citation count |
| A4 | **단순 파이프라인과 비교.** 고정 컬렉션에서 "검색 1회 → 답변"(naive RAG)과 현행 에이전트를 같은 세트로 비교한다 | 더 단순한 쪽이 비기면 단순한 쪽을 택한다. CRAG(Yan et al., 2024)와 Self-RAG(Asai et al., 2023)는 다중 홉이나 답 없음 케이스에서 실패가 확인된 뒤에 검토한다. GraphRAG는 논문 3편 규모의 코퍼스에는 과하다 | 지연과 토큰 감소 가능성(LLM 1~2콜 고정) [추정] | M | 다문서 비교 질문에서 품질이 떨어질 수 있다 | 전 지표 + p95 |
| A5 | 컨텍스트 순서. 상위 청크를 처음과 끝에 둔다 | Liu et al., 2024, *Lost in the Middle* (TACL). k≤8이라 효과는 작을 것이다 | 작다 [추정] | S | 없음 | faithfulness |
| A6 | 멀티턴 이력 전달(P19) | 기능 결함 | 이 평가 세트로는 측정할 수 없다. 멀티턴 케이스를 추가해야 한다 | M | 이력만큼 토큰이 늘어난다 | 멀티턴 케이스 정답률 |

---

## 4. 실험 순서 (한 번에 하나)

원칙: 한 번에 변수 하나만 바꾼다. 나머지(모델, temperature 0, 데이터셋, judge)는 고정한다. 검색 변경은 먼저 **E2 오프라인 지표**로 거르고, 통과한 것만 E2E를 돌린다. 튜닝은 dev 분할에서만 하고, test 분할은 최종 보고에만 쓴다.

| 단계 | 라벨(`EVAL_LABEL`) | 변경 | 주 지표 | 채택 조건 |
|---|---|---|---|---|
| 0 | ~~`baseline-fixed-r{1,2,3}`~~ | E1 id 재매핑 | - | **완료**(v2 하네스에 흡수, 파일명으로 id 해석) |
| 1 | `baseline-v2` | E3 + E4 + E5 첫 단계 (지표, 110건 세트, judge 교체) | recall, groundedness, 행동 통과율 | **완료 1회**(§1.1). 남은 일: 2회 더 돌려 분산 기록(E6), P23 임계값 결정 |
| 2 | `a1-force-search` | A1 | groundedness, 행동 통과율(ko/en-rag), recall | RAG 행동 통과율 상승, nonrag 회귀 없음 |
| 3 | `a3-docs-before-web` | A3 (순서를 앞당김, P20/P21) | 행동 통과율, 웹 인용 수, input tokens | 금지 도구 호출 감소, 품질 회귀 없음 |
| 4 | `a2-full-chunk` | A2 | correctness, meanToolCalls, input tokens | 토큰이 늘지 않거나 품질 개선으로 정당화될 것 |
| 4b | `m1-chunk-{256,512}tok` | M1 (변형마다 컬렉션 하나) | Recall@5, MRR (오프라인) → E2E | 오프라인 MRR 개선이 CI 밖일 것 |
| 5 | `m2-e5-prefix` | M2 | MRR | 회귀 없음 (비용이 0이라 동률이어도 채택) |
| 6 | `r1-title-header` | R1 (제목만) | hard negative 문서 P@k | 개선 |
| 7 | `r3-fusion-*` | dense 단독 / RRF k=60 / 가중 RRF | Recall@8, MRR | 최고 변형 채택 |
| 8 | `r2-rerank-{jina,bge}` | R2 (depth 30~50 → k=5) | nDCG@5, latency | nDCG 개선과 p95 증가 < 0.5 s |
| 10 | `m3-emb-*`, `r4-kiwi` | 한국어 세트에서 모델 비교, Kiwi BM25 | Recall@k, MRR | 측정 후 결정 |
| (나중) | `r1b-contextual-llm`, `a4-naive` | LLM 문맥 헤더, 단순 파이프라인 | 위와 같음 | 단순한 쪽이 비기면 단순한 쪽 |

보고 형식(포트폴리오용): `변경 X: MRR@5 0.67 → 0.81 (95% CI +0.08~+0.19), 입력 토큰 8.2k → 6.1k, p95 10.8 s → 9.9 s, 인제스트 비용 +0`.

---

## 5. 다시 돌리고 비교하는 법

```bash
# 사전 조건: eval/README.md "Prerequisites" (infra, backend, eval/.env)
cd eval
npm run ingest:v2                                   # rag_eval_v2 준비. API와 ingest worker가 떠 있어야 한다. 다시 돌려도 안전하다
EVAL_DATASET=all EVAL_LABEL=m2-e5-prefix npm test   # 110건 전부
EVAL_DATASET=ko-rag,en-rag EVAL_LABEL=m2-e5-prefix-rag npm test   # 일부 데이터셋만
# → eval/results/<YYYY-MM-DD>-<label>.json / .md (같은 날짜+라벨이면 덮어쓴다)
```

- **비교 대상:** 결과 `.md`의 "Aggregates by dataset"(`passCount`, `meanRecall`, `meanPrecision`, `meanCorrectness`, `meanGroundedness`, `behaviorPassRate`, `meanInputTokens`, `meanToolCalls`, `latencyP50Ms/P95Ms`)를 데이터셋별로 `2026-11-21-baseline-v2`와 나란히 놓는다. 이전 `baseline-r1/r2`는 옛 9건 세트라서 v2와 비교하지 않는다. judge도 바뀌었으니 judge 점수를 r1/r2와 비교하면 안 된다. 케이스별 비교는 `.json`의 `cases[].result`(answer, citations, toolCalls, judgeReasoning)로 한다. 같은 `id`끼리 맞춰 보면 된다.
- **회차 간 분산:** v2 기준선은 아직 1회뿐이라 v2 분산은 모른다. 비교하기 전에 기준선을 2회 더 돌린다. 참고로 옛 세트에서는 같은 설정의 r1과 r2가 judge 0.911 vs 0.944, 입력 토큰 8168 vs 7905, p50 5.7 vs 6.3 s로 달랐다. **이보다 작은 차이는 개선이 아니다.** 변형마다 3회 이상 돌려 평균 ± 범위를 보고하고, 세트가 커지면 paired bootstrap CI를 쓴다.
- **바뀐 설정은 결과 메타에 남는다.** `meta`(gitSha, top_k, 청크 크기, 임베딩 모델)를 확인해서 의도한 변수 하나만 달라졌는지 검증한다. 인제스트 변경(M1, M2, R1)은 변형마다 컬렉션을 따로 만들고 golden의 `collectionName`을 바꾼다.
- **검색만 바꾼 실험**은 E2 오프라인 스크립트를 먼저 돌린다(LLM 비용 0, 결정적). E2E는 통과한 변형만 돌린다.
- 결과는 `docs/harness/LLM_SPECIFICATION.md`의 측정 이력 표와 `DECISION_LOG.md`(채택 결정과 근거 수치)에 기록한다.

---

## 부록 A. 오프라인 검색 프로브 (T-028, 직접 측정)

**방법.** `rag_eval_papers`의 69개 포인트(저장된 dense와 sparse 벡터 포함)를 읽기 전용 scroll로 받았다. Qdrant와 같은 식으로 로컬에서 검색을 재현했다: dense 코사인, BM25 × idf(`ln((N-n+0.5)/(n+0.5)+1)`), RRF `1/(pos+k)`, k=2, prefetch 8. 운영(V0)을 재현한 결과는 라이브 Qdrant `query_points`와 **top-8이 72/72 일치**했다. 변형은 같은 fastembed 모델로 다시 임베딩했다. 청크 재분할은 저장된 청크를 중첩 제거로 원문 복원한 뒤 다시 잘랐다.

**라벨.** 문서 단위 라벨은 케이스의 논문이다. 청크 단위 라벨은 **정규식 silver 라벨**이다. 정답 논문 안에서 핵심 문자열(`h = 8`, `28.4`, `extremely small gradients`, `Next Sentence Prediction`, `340M`, `80%`, `BooksCorpus`, `768`, `14.8`)을 포함한 청크를 정답으로 봤고, 사람이 검수하지 않았다.

**한계.** n=9라서 Hit 계열은 케이스 하나가 0.111이다. golden 질의 원문을 썼고, 에이전트가 실제로 보내는 재작성 질의와는 다르다. 청크 크기가 다르면 silver 라벨 수도 달라서 recall은 엄밀히 비교되지 않는다. **방향을 보는 용도이고, 채택 근거로 쓰면 안 된다.**

| 변형 | 문서 P@8 | Hit@3 | Hit@8 | MRR@8 | Recall@8 | 문서 P@8 (GPT 3건) |
|---|---|---|---|---|---|---|
| V0 운영 재현 (저장 벡터, 접두사 없음, RRF k=2, prefetch 8) | 0.667 | 0.778 | 0.778 | 0.667 | 0.750 | 0.208 |
| V1 dense 단독 (저장 벡터) | 0.722 | 0.778 | 0.889 | 0.736 | 0.713 | 0.458 |
| V2 BM25 단독 (저장 벡터) | 0.625 | 0.667 | 0.778 | 0.578 | 0.611 | 0.083 |
| V0b 운영 + prefetch 50 | 0.653 | 0.778 | 0.778 | 0.667 | 0.750 | 0.167 |
| V3 V0 + e5 접두사 | 0.667 | 0.778 | 0.778 | 0.722 | 0.750 | 0.208 |
| V3d dense 단독 + 접두사 | 0.694 | 0.778 | 0.778 | 0.778 | 0.657 | 0.375 |
| V4 V3 + 청크별 제목 헤더 | 0.708 | 0.778 | 0.778 | 0.667 | 0.694 | 0.333 |
| V4d dense 단독 + 접두사 + 헤더 | 0.750 | 0.778 | 0.778 | 0.667 | 0.657 | 0.500 |
| **V5 V4 + 300단어 청크 (≈512토큰 이하, 93청크)** | **0.792** | **0.889** | **0.889** | **0.815** | **0.833** | **0.542** |
| V6 V4 + 150단어 청크 (184청크) | 0.806 | 0.889 | 0.889 | 0.722 | 0.700 | 0.542 |

한국어 질의(같은 9문항을 작성자가 번역, 영어 코퍼스 그대로):

| 변형 | 문서 P@8 | Hit@3 | Hit@8 | MRR@8 | Recall@8 | 문서 P@8 (GPT 3건) |
|---|---|---|---|---|---|---|
| K0 운영 재현, 한국어 질의 | 0.694 | 0.556 | 0.889 | 0.560 | 0.694 | 0.292 |
| K1 dense 단독, 한국어 질의 | 0.708 | 0.889 | 0.889 | 0.704 | 0.657 | 0.375 |
| K2 BM25 단독, 한국어 질의 | 0.222 | 0.222 | 0.222 | 0.222 | 0.222 | 0.000 |
| K4 V4 (접두사 + 헤더), 한국어 질의 | 0.708 | 0.667 | 0.778 | 0.608 | 0.639 | 0.292 |
| K4d V4 dense 단독, 한국어 질의 | 0.806 | 0.667 | 0.889 | 0.649 | 0.657 | 0.542 |

읽는 법: 한국어 질의에서는 BM25가 질의 속 영어 고유명사 몇 개만 겨우 맞힌다(K2). 그 BM25가 RRF로 섞이면 Hit@3이 0.889(K1)에서 0.556(K0)으로 떨어진다. 한국어 질의로 영어 문서를 찾는 상황에서는 **지금의 hybrid가 dense 단독보다 해롭다.** 150단어(V6)는 문서 P@8은 높지만 MRR과 Recall이 300단어(V5)보다 낮다. 청크가 너무 작으면 사실 하나가 여러 청크로 갈라진다(context miss).

프로브 스크립트는 [`eval/results/2026-11-21-probe/`](../eval/results/2026-11-21-probe/)에 그대로 보관했다(입력 덤프 방법은 파일 머리 주석 참고). E2를 구현할 때 같은 로직을 `eval/`에 정식으로 옮긴다.

## 부록 B. 참고 문헌 (근거 강도)

- Cormack, Clarke, Büttcher. *Reciprocal Rank Fusion outperforms Condorcet and Individual Rank Learning Methods.* SIGIR 2009. 강함(k=60 제안)
- Wang et al. *Multilingual E5 Text Embeddings: A Technical Report.* 2024. 모델 사양(접두사, 512토큰)
- Chen et al. *BGE M3-Embedding: Multi-Lingual, Multi-Functionality, Multi-Granularity Text Embeddings.* 2024. 중간(저자 벤치마크)
- Anthropic. *Introducing Contextual Retrieval.* 2024 블로그. 약~중간(동료 심사 없음, 자체 데이터)
- Nogueira, Cho. *Passage Re-ranking with BERT.* 2019. 강함
- Liu et al. *Lost in the Middle: How Language Models Use Long Contexts.* TACL 2024. 강함(긴 컨텍스트에서. 짧은 k에서는 효과가 작다)
- Es et al. *RAGAS: Automated Evaluation of Retrieval Augmented Generation.* 2023. 중간(faithfulness 지표 정의)
- Zheng et al. *Judging LLM-as-a-Judge with MT-Bench and Chatbot Arena.* 2023. Panickssery et al. *LLM Evaluators Recognize and Favor Their Own Generations.* 2024. 중간(judge 편향)
- Mallen et al. *When Not to Trust Language Models: Investigating Effectiveness of Parametric and Non-Parametric Memories.* ACL 2023. 강함(유명 지식은 기억으로 답한다)
- Yan et al. *Corrective Retrieval Augmented Generation.* 2024. Asai et al. *Self-RAG.* 2023. 중간(이 규모에는 아직 불필요)
- Gao et al. *Precise Zero-Shot Dense Retrieval without Relevance Labels (HyDE).* 2022. 중간. 질의 재작성 계열은 E5 세트에서 다중 홉 실패가 확인된 뒤에 검토한다
