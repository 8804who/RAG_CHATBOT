# 부하 테스트 시나리오

`loadtest/`의 Locust 코드(진입점 `locustfile.py`, 패키지 구성은 [README.md](README.md))가 구현하는 시나리오의 설계 문서다. 시나리오마다 무엇을 하고, 왜 골랐고, 무엇을 합격으로 보는지를 적는다. 실행 방법은 [README.md](README.md)에 있다.

> 출처 대부분은 벤더 블로그와 도구 문서다. 생각 시간, 스파이크 배수, soak 길이 같은 숫자는 업계에서 흔히 쓰는 값이지 표준이 아니다. 이 시스템에 맞춰 고른 값은 "가정"으로 따로 표시했다.

## 1. 목적과 측정 범위

LLM을 mock(`mock_openai.py`, 호출 1회 800±300ms)으로 바꿔 **우리 인프라만** 잰다. 실제 LLM은 호출 1회에 1~30초가 걸리고 편차도 크다. 그대로 두면 LLM 지연에 가려 우리 쪽 처리량 한계가 보이지 않는다. 그래서 LLM은 응답 형태가 실제와 같고 지연을 조절할 수 있는 mock으로 바꾼다 ([S4](https://docs.databricks.com/aws/en/generative-ai/agent-framework/load-test-agent-app)).

| 측정함 (실제 코드 경로) | 측정 안 함 |
|---|---|
| FastAPI + 단일 uvicorn 프로세스의 이벤트 루프 | LLM 제공자 지연·RPM/TPM 한도·429 (mock) |
| SQLAlchemy 커넥션 풀 / Postgres 쓰기 (메시지, usage log, tool-call log) | 답변 품질 (`eval/` 담당) |
| LangGraph `create_agent` 그래프 생성·실행 오버헤드 (턴당 LLM 2회, 도구 1회) | 다단계 도구 루프 (mock은 검색 1회 후 바로 답함) |
| Qdrant 하이브리드 검색 (`get_collection` + RRF query) | 웹 검색/arXiv 도구 (mock이 호출 안 함) |
| **질의 임베딩: 기본 컬렉션 `rag_eval_papers`는 fastembed `multilingual-e5-large`(로컬 CPU)라 mock이 아니라 실제 연산이 돈다** | Langfuse 오버헤드 (부하 실행 시 비활성) |
| 세션 쿠키 인증 (요청마다 DB 조회 2회: 미들웨어 + `get_current_user`) | 인제스트 파이프라인 (Kafka/워커) → §7 향후 시나리오 |
| | 네트워크 지연 (localhost), 프론트 렌더링 |

## 2. 사용자 모델

시나리오는 "누가 몇 명인지"만 바꾼다. 사용자 행동은 모든 시나리오에서 같다.

| 항목 | 값 | 이유 |
|---|---|---|
| `ChatUser` weight | 4 | 가정: 주 사용 흐름은 채팅 |
| `BrowseUser` weight | 1 | 가정: 컬렉션·문서·사용량 화면은 부수 흐름. 비율은 Locust KL 분배라 3명이면 Chat 2 + Browse 1 |
| 대화 단위 | 세션 1개 = 페이지 진입 → 채팅 생성 → 1~5턴 (`randint(1,5)`, 평균 3) | LLM 챗봇 부하는 단발 요청이 아니라 생각 시간이 있는 다중 턴 세션으로 모델링해야 한다 ([S5](https://tianpan.co/blog/2026-03-19-load-testing-llm-applications), [S6](https://callsphere.ai/blog/load-testing-ai-agent-systems-10000-conversations)) |
| ChatUser 생각 시간 | `wait_time = between(3, 10)` 초, 매 턴 전과 세션 끝에 적용 | S6은 2~8초를 쓴다. 여기서는 RAG 답변을 읽는 시간을 더해 조금 길게 잡았다 (가정, 평균 6.5초) |
| BrowseUser 대기 | `between(2, 5)` 초 | 가정: 목록 화면은 타이핑이 없어서 더 빠르다 |
| pinned / routed | ChatUser 생성 순번 `n`(클래스 전용 0부터 세는 카운터)이 `n % 3 == 1`이면 routed(`collection_name` 생략), 나머지는 pinned. 사용자 수명 동안 고정 | 프론트 기본값은 첫 컬렉션 고정이고, "Let the agent choose"는 사용자가 골라야 켜진다. routed 비율 1/3은 가정이다. 랜덤 대신 순번으로 정해서 smoke(ChatUser 2명)도 두 모드를 반드시 거친다 |
| 질의 코퍼스 | `../eval/fixtures/golden-dataset.json`의 `query` 9개를 무작위로 사용. 모델은 데이터셋의 `chatModel`(`gpt-4o-mini`) | 이미 인제스트된 실제 코퍼스라 pinned 검색이 항상 결과를 낸다. 질의 길이 53~153자 |
| 시드 사용자 할당 | Locust 사용자 생성 순번(두 클래스 공용 카운터) `% N`으로 시드 사용자를 고른다 | 반납 관리가 필요 없다. spike 재생성으로 같은 사용자를 두 Locust 사용자가 함께 쓸 수 있지만 무해하다 |
| 요청 타임아웃 | 모든 요청 60초 | 풀 대기 한도(`pool_timeout` 30초) + LLM 2회보다 길게 잡는다. 그래야 서버 쪽 포화가 클라이언트 타임아웃이 아니라 서버 500으로 드러난다 |

**ChatUser 세션 (task 1개):**

| 순서 | 요청 | Locust `name` | 검증 (`catch_response`) |
|---|---|---|---|
| 1 | `GET /api/v1/auth/me`, `GET /api/v1/models`, `GET /api/v1/collections` (사이 대기 없음 = 페이지 로드) | 경로 그대로 | 200 |
| 2 | `POST /api/v1/chats` `{chat_model, collection_name?}` | `/api/v1/chats` | 201, `id` 비어있지 않음 |
| 3 | 턴마다: `self.wait()` 후 `POST /api/v1/chats/{id}/messages` `{query}` | `/api/v1/chats/[chat_id]/messages` | §5 내용 검증 |
| 4 | task 종료 → Locust가 `wait_time`을 한 번 더 적용 (세션 사이 간격) | | |

**BrowseUser (task 1개):** `GET /api/v1/collections` → wait → `GET /api/v1/collections/{C}/documents` (`name=/api/v1/collections/[name]/documents`) → wait → `GET /api/v1/usage/stats`. 응답은 200만 확인한다.

**인증 우회:** 테스트 시작(`test_start`, 첫 사용자 spawn 전)에 시드 사용자 N명(N = 선택한 시나리오의 최대 사용자 수, §4)을 넣는다. `users`에는 `google_sub='loadtest-{i}'`, `email='loadtest-{i}@loadtest.invalid'`로 `ON CONFLICT (google_sub)` upsert하고, `google_sessions`에는 `token=secrets.token_urlsafe(32)`, `expires_at=now()+24h`로 넣는다. 토큰은 쿠키 `session`으로 보낸다. 테스트 종료(`test_stop`)에 이 세션만 지우고 사용자 행은 다음 실행에서 재사용한다. 방식은 `eval/src/db.ts`와 같고, DB 접속도 같은 `POSTGRES_*` env를 쓴다. 24시간 만료는 가장 긴 soak(4시간)보다 길어서, 강제 종료로 세션이 남더라도 하루 안에 만료된다.

## 3. 환경 변수

| 변수 | 기본값 | 의미 / 존재 이유 |
|---|---|---|
| `LOADTEST_SCENARIO` | `smoke` | `smoke\|load\|stress\|spike\|soak\|breakpoint`. 다른 값이면 import 시점에 유효값 목록을 출력하고 즉시 종료 (FR-009 (2)) |
| `LOADTEST_TARGET_USERS` | `50` | **T** = 예상 피크 동시 사용자. smoke를 뺀 모든 단계 목표가 T의 배수다. 정수 ≥ 1이 아니면 즉시 종료. 기본 50은 §6 가설에서 예측한 무릎(약 115~145명) 아래에 load를, 무릎 근처에 stress를, 무릎 위에 spike를 두는 값이다 |
| `LOADTEST_COLLECTION` | 데이터셋의 `collectionName` (`rag_eval_papers`) | pinned 모드 컬렉션이자 BrowseUser 문서 목록 대상이다. 문서가 1개 이상 있어야 한다. H2를 검증하는 A/B 레버이기도 하다 (§6) |
| `LOADTEST_CHAT_P95_MS` | `3000` | 채팅 턴 p95 SLO. 합격 게이트와 breakpoint 정지 규칙이 이 값을 쓴다. mock의 `MOCK_LATENCY_MS`/`MOCK_JITTER_MS`를 바꾸면 `2×(LATENCY+JITTER)+1000`으로 맞춘다 |
| `POSTGRES_HOST/PORT/USER/PASSWORD/DB` | `localhost`/`5432`/—/—/— | 시드용 DB 접속 정보. `eval/`과 백엔드 `.env`의 이름을 그대로 쓴다 (새 변수 아님) |

일부러 만들지 않은 변수는 세 가지다. 채팅 모델은 데이터셋 값을 쓴다. routed 비율은 1/3로 고정한다. 대상 호스트는 Locust의 `-H`가 이미 받는다.

## 4. 시나리오

### 공통 규칙 (단계표 해석)

- `u(x) = max(1, ceil(x × T))`. 예시 열은 T=50 기준이다.
- 단계 = `(길이, 목표 배수, 램프 시간)`. 단계가 시작되면 직전 단계의 목표(첫 단계는 0)에서 `u(배수)`까지 **램프 시간 동안 선형 보간**한다. 램프가 끝나면 남은 시간은 그 값을 유지한다. 매 tick의 목표는 `ceil(prev + (u − prev) × min(1, 경과/램프))`이고, 램프가 0이면 즉시 목표로 간다.
- `tick()`은 `(목표, 100)`을 반환한다. spawn rate는 100으로 고정이다. 램프를 spawn rate로 만들지 않고 매초 바뀌는 목표값으로 만드는 이유는, 그래야 사용자 수가 매초 위 공식대로 정확히 정해지기 때문이다. Locust의 spawn rate 동작은 runner 종류마다 다르다. 우리가 쓰는 `LocalRunner.start`는 진행 중인 spawn greenlet을 죽이고 새로 띄운 뒤 바로 반환한다(`locust/runners.py` `LocalRunner.start`). 분산 실행의 master runner는 `start()`가 램프를 끝낼 때까지 shape worker를 막는다(`shape_worker`의 TODO 주석). 목표값 보간은 이 차이에 기대지 않고, breakpoint 정지 규칙과 `-t` 상한도 매초 `tick()`에서 평가된다.
- 시드(`test_start`)가 끝나기 전(세션 풀이 비었거나 runner가 `STATE_INIT`)에는 `tick()`이 `reset_time()`을 부르고 `(0, 100)`을 반환한다. 시드는 spawn greenlet 안에서 돌고 psycopg가 gevent에서 양보하므로, tick 값이 바뀌어 `LocalRunner.start`가 다시 불리면 시드가 kill되고 처음부터 다시 시작된다. 같은 tick을 유지하면 `start()`가 다시 불리지 않는다. 그래서 `get_run_time()`은 시드 완료 시점부터 센다.
- 모든 단계가 끝나면 `tick()`은 `None`을 반환해 테스트를 끝낸다.
- **`-t/--run-time`은 shape가 직접 지킨다.** headless 모드에서 shape를 쓰면 Locust는 `-t`를 무시한다(`locust/main.py`: shape greenlet을 join한 뒤에야 run-time 타이머를 걸고, 그 전에 "will be ignored" 경고를 낸다, [S11](https://docs.locust.io/en/stable/custom-load-shape.html)). 그래서 `use_common_options = True`로 두고, `environment.parsed_options.run_time`(초)이 있으면 `get_run_time() ≥ run_time`일 때 `None`을 반환한다. 이 시계는 시드 완료부터 세므로 `-t`에 시드 시간은 들어가지 않는다. 시드가 멈추면 `-t`도 그만큼 늦어지고, 시드 실패는 `-t`와 관계없이 바로 exit 1로 끝난다. Ctrl+C도 정상 종료(통계 기록, 세션 삭제)된다.
- 시드 사용자 수 N = 표의 최대 사용자 수 (smoke 3, load T, stress 2T, spike 3T, soak T, breakpoint 10T).

권장 실행 순서: smoke → load → stress → spike → breakpoint → soak. 작게 시작해서 늘려 간다 ([S10](https://reintech.io/blog/llm-load-testing-benchmark-ai-application-production)). 앞 단계가 실패하면 다음 단계 결과는 해석할 수 없다.

### 4.1 smoke

| 단계 | 길이 | 목표 | 램프 | 누적 종료 | T=50 |
|---|---|---|---|---|---|
| 1 | 2분 | **3명 고정** (T 무관) | 0 | 2:00 | 3 (Chat 2: pinned 1 + routed 1, Browse 1) |

- 목적: 스크립트·mock·시드·검증 규칙이 실제 스택에서 맞물리는지 확인한다. 다른 시나리오를 돌리기 전 관문이다.
- 드러나는 것: 설정 오류(백엔드가 mock을 안 가리킴, 컬렉션 비어 있음, 시드 실패), 검증 규칙 오탐.
- 합격: 전체 실패 **0**, 채팅 턴 요청 ≥ 2, 채팅 턴 p95 ≤ SLO.
- 이유: 최소 부하로 스크립트와 시스템이 정상 동작하는지 먼저 확인하는 것이 모든 후속 테스트의 기준선이다 ([S1](https://grafana.com/load-testing/types-of-load-testing), [S2](https://grafana.com/docs/k6/next/testing-guides/test-types.md)).

### 4.2 load (평균 부하)

| 단계 | 길이 | 목표 | 램프 | 누적 종료 | T=50 |
|---|---|---|---|---|---|
| 1 | 5분 | 1.0T | 5분 | 5:00 | 0→50 |
| 2 | 30분 | 1.0T | — | 35:00 | 50 |

- 목적: 예상 피크에서 SLO를 지키는지 확인한다. 이후 시나리오와 비교할 기준선이다.
- 드러나는 것: 정상 부하의 p50/p95, 풀 사용률 기준값.
- 합격: 실패율 ≤ 1%, 채팅 턴 p95(전 구간) ≤ SLO.
- 이유: 평균 부하 테스트는 예상 운영 부하에서 성능 목표를 검증하는 기본 유형이다. 짧은 램프 뒤 30분 이상 유지하는 구성이 흔하다 ([S2](https://grafana.com/docs/k6/next/testing-guides/test-types.md)).

### 4.3 stress

| 단계 | 길이 | 목표 | 램프 | 누적 종료 | T=50 |
|---|---|---|---|---|---|
| 1 | 5분 | 1.0T | 5분 | 5:00 | 0→50 |
| 2 | 10분 | 1.0T | — | 15:00 | 50 (같은 실행 안의 기준선) |
| 3 | 5분 | 2.0T | 5분 | 20:00 | 50→100 |
| 4 | 30분 | 2.0T | — | 50:00 | 100 |

- 목적: 피크의 2배에서도 SLO를 지키는지, 즉 여유가 2배 이상인지 확인한다.
- 드러나는 것: 무릎에 가까워질 때의 p95 상승. §6 가설로는 DB 풀 사용률이 약 70%가 되는 구간이다.
- 합격: load와 같다 (실패율 ≤ 1%, p95 ≤ SLO). 불합격은 버그가 아니라 "여유가 2배 미만"이라는 정보다.
- 이유: 스트레스 테스트는 평균보다 높은 부하를 유지하면서 성능이 어떻게 떨어지는지 본다 ([S1](https://grafana.com/load-testing/types-of-load-testing), [S3](https://trailhead.salesforce.com/de/content/learn/modules/performance-testing-basics/learn-about-performance-testing-types)). 같은 실행 안에 1× 구간을 넣어 두면 실행 간 편차 없이 1×와 2×를 바로 비교할 수 있다.

### 4.4 spike

| 단계 | 길이 | 목표 | 램프 | 누적 종료 | T=50 |
|---|---|---|---|---|---|
| 1 | 5분 | 0.3T | 1분 | 5:00 | 0→15 (평시) |
| 2 | 10분 | 3.0T | 30초 | 15:00 | 15→150 (급증 후 유지) |
| 3 | 10분 | 0.3T | 10초 | 25:00 | 150→15 (회복 관찰) |

- 목적: 갑작스러운 3배 유입에서 서버가 죽거나 대기열을 남기지 않는지, 부하가 빠진 뒤 원래대로 돌아오는지 확인한다.
- 드러나는 것: 포화 시 동작(지연만 오르는지, 500이 나는지, 프로세스가 죽는지)과 회복 시간.
- 합격 (수동 판정, `--csv-full-history` 이력의 채팅 턴 행 기준): 백엔드 프로세스 생존, **17:00~25:00**(하강 2분 뒤부터) 구간의 current p95 ≤ SLO, 실패 0. 급증 구간(5:30~15:00)의 p95와 실패율은 기록만 한다. §6 예측은 "p95는 SLO를 넘고, 오류는 0, 하강 후 1분 안에 회복"이다.
- 이유: 스파이크는 스트레스의 하위 유형이다 ([S3](https://trailhead.salesforce.com/de/content/learn/modules/performance-testing-basics/learn-about-performance-testing-types)). LLM 게이트웨이는 평시 30%에서 200~300%로 갑자기 올려 10~15분 유지하고, 그 뒤 회복을 보는 구성을 권한다 ([S7](https://gravitee.io/corpus/gen-1448/test-management/llm-gateway-load-testing.html)). S7이 경고하는 재시도 폭주는 재현하지 않는다. Locust 사용자는 재시도하지 않는다 (§7).

### 4.5 soak

| 단계 | 길이 | 목표 | 램프 | 누적 종료 | T=50 |
|---|---|---|---|---|---|
| 1 | 5분 | 1.0T | 5분 | 5:00 | 0→50 |
| 2 | 3시간 55분 | 1.0T | — | 4:00:00 | 50 |

- 목적: 오래 돌려야만 드러나는 문제를 찾는다. 커넥션 누수, 메모리 증가, 로그 테이블 증가에 따른 쿼리 저하가 대상이다.
- 드러나는 것: T=50이면 4시간에 약 5.4만 턴이 쌓인다. 행으로는 `chat_messages` 약 11만, `chat_usage_logs`·`agent_tool_call_logs` 각 약 5.4만, `chats` 약 1.8만이다. `/usage/stats`는 사용자별 집계라 요청자 행이 늘수록 느려질 수 있다.
- 합격: 자동 게이트(실패율 ≤ 1%, p95 ≤ SLO)에 더해 수동 확인 세 가지: (a) 채팅 턴 current p95의 마지막 30분 중앙값 ≤ 5:00~35:00 구간 중앙값 × 1.2 (b) API 프로세스 RSS가 30분 시점 대비 종료 시점 +10% 이내 (c) 앱 DB의 `pg_stat_activity` 연결 수가 내내 ≤ 16 (풀 15 + 여유 1)
- 길이: 기본 4시간이다. `-t`로 줄일 수 있지만, 그러면 누수 검출력이 떨어진다는 점을 결과에 적는다.
- 이유: 소크는 평균 부하를 오래 유지해 시간이 지나야 쌓이는 결함을 찾는다 ([S2](https://grafana.com/docs/k6/next/testing-guides/test-types.md)). LLM 앱에서는 풀 고갈과 누수가 몇 시간 뒤에야 나타나므로 4시간 이상을 권한다 ([S5](https://tianpan.co/blog/2026-03-19-load-testing-llm-applications)).

### 4.6 breakpoint

| 단계 | 길이 | 목표 | 램프 | 누적 종료 | T=50 |
|---|---|---|---|---|---|
| 1 | 최대 30분 | 10.0T | 30분 (선형) | 30:00 | 0→500 (초당 약 0.28명) |

- 목적: 무릎(처리량이 더 늘지 않고 지연이 SLO를 넘는 지점)의 사용자 수를 찾는다. §6 가설을 확증하거나 반증하는 주 시나리오다.
- 드러나는 것: 한계 사용자 수와 그때 먼저 포화되는 자원 (§6 신호표).
- **자동 정지 규칙.** 대상 엔트리는 `E = runner.stats.get("/api/v1/chats/[chat_id]/messages", "POST")`이고, 매 tick(약 1초)마다 평가한다.
  1. 유예: `get_run_time() < 120`이면 평가하지 않는다(시계는 `-t`와 같이 시드 완료부터 센다). 다만 아래 스냅샷은 계속 쌓는다.
  2. 스냅샷: 매 tick `(t, E.num_requests, E.num_failures)`를 deque에 넣고 최근 61개만 유지한다.
  3. **오류 조건 F:** 최근 60초 창에서 `Δreq ≥ 20`이고 `Δfail / Δreq > 0.05`이면 즉시 정지한다.
  4. **지연 조건 L:** `p = E.get_current_response_time_percentile(0.95)`(Locust 내장, 약 10초 슬라이딩 창). 이번 tick의 위반 여부는 `p is not None and p > LOADTEST_CHAT_P95_MS and (최근 10초 Δreq ≥ 10)`으로 정한다. 위반이면 `streak += 1`, 아니면 `streak = 0`이다. streak가 0에서 1이 되는 순간의 사용자 수를 `onset_users`로 기록한다. **streak ≥ 30**(30초 연속 위반)이면 정지한다. 램프가 초당 0.28명이므로 확인하는 30초 동안 초과하는 양은 약 8명이다.
  5. 정지할 때 `logger.warning`으로 `breakpoint reached: reason=<latency|errors>, onset_users=…, users_now=…, chat_p95=…, window_fail_ratio=…`를 남기고 `tick()`이 `None`을 반환한다. **한계 = 지연 조건이면 `onset_users`, 오류 조건이면 `users_now`.**
  6. 30분 램프를 정지 없이 끝내면 `no breakpoint up to 10×T`를 남긴다. T를 올려 다시 실행한다.
- 합격: 해당 없음. 결과는 한계 사용자 수이고, §6 예측(T=50에서 약 115~150명)과 비교한다. 정지 조건 F가 걸렸다면 Locust 기본 동작대로 exit code가 1이 될 수 있다.
- 이유: breakpoint는 비현실적인 수준까지 점진적으로 올려 한계를 찾고, 임계치를 넘으면 스스로 멈추게 하는 유형이다 ([S1](https://grafana.com/load-testing/types-of-load-testing), [S2](https://grafana.com/docs/k6/next/testing-guides/test-types.md)). 램프를 올리며 용량의 무릎을 찾는 것은 LLM 게이트웨이 테스트의 핵심 절차다 ([S7](https://gravitee.io/corpus/gen-1448/test-management/llm-gateway-load-testing.html)). 유예 시간과 연속 위반 조건은 k6 임계치의 `abortOnFail` + 평가 지연과 같은 목적이다. 순간 노이즈로 멈추지 않게 한다.

## 5. SLO와 합격 기준

속도 관문과 품질 관문을 따로 둔다. RAG는 200 OK만으로 정상이라고 볼 수 없다. 검색이 조용히 깨져도 200이 나오기 때문이다 ([S8](https://loadforge.com/guides/ai-llm/load-test-rag-applications), [S9](https://dzone.com/articles/performance-testing-rag-applications)).

**속도 관문**

| 지표 | 기준 | 근거 |
|---|---|---|
| 채팅 턴 p95 | ≤ `LOADTEST_CHAT_P95_MS` (3000ms) | mock 2회 호출은 각각 U(500,1100)ms이고, 합의 p95는 2200 − 600·√0.1 ≈ **2010ms**다. 경합이 없을 때 인프라 몫(e5 임베딩 + Qdrant 2회 + DB 5~6회 + 그래프)은 약 0.1~0.3초로 예상하므로 예상 p95는 약 2.3초다. SLO에는 인프라 몫 약 1초를 허용한다 |
| 그 외 요청 p95 | ≤ 500ms | 보고용이고 게이트는 아니다. DB 조회·Qdrant 목록만 하는 요청이다 |
| 실패율 (Aggregated) | smoke 0건, load/stress/soak ≤ 1% | |

**품질 관문 (요청 단위, `catch_response`).** 실패 메시지를 분류해 두면 Locust Failures 탭에서 속도 실패와 품질 실패가 섞이지 않는다.

채팅 턴은 표의 순서대로 검사하고, 처음 실패한 규칙 하나만 기록한다.

| 규칙 | 실패 메시지 |
|---|---|
| status ≠ 200 | `http <code>` |
| `content`가 비었거나 공백뿐 | `empty content` |
| `content`가 `[mock]`으로 시작하지 않음. 백엔드가 실제 OpenAI를 부르고 있다는 뜻이므로 과금 방지를 위해 **즉시 `environment.runner.quit()`**. 인용 검사보다 먼저 하므로, 인용이 없는 실제 OpenAI 답변도 계속 진행되지 않고 종료된다 | `non-mock answer` |
| pinned인데 `citations == []`. `DEFAULT_RETRIEVAL_TOP_K=8`이고 점수 하한이 없어서, 문서가 있는 컬렉션이면 항상 인용이 나와야 한다. 빈 인용은 검색이 조용히 깨졌다는 뜻이다 | `empty citations (pinned)` |
| routed는 `content`만 검사한다. mock이 카탈로그의 첫 컬렉션을 고르는데, 그 컬렉션이 비어 있을 수 있다 | — |
| (채팅 생성) `POST /chats`가 201이 아니면 `http <code>`, 201인데 `id`가 없으면 그 사용자는 턴을 보내지 않는다 | `empty chat id` |

**자동 게이트** (`events.quitting`, smoke/load/stress/soak에만): 위 속도 기준(채팅 턴 전 구간 p95, Aggregated 실패율, smoke는 채팅 턴 ≥ 2건)을 어기면 원인을 로그로 남기고 `environment.process_exit_code = 1`로 둔다. spike와 breakpoint는 §4의 수동 판정 또는 정지 로그로 판단한다.

## 6. 용량 가설 (먼저 막힐 곳)

**부하 모델 (T와 무관한 1인당 값):**

- ChatUser 1사이클: 페이지 진입·채팅 생성 0.2초 + 3턴 × (생각 6.5초 + 턴 1.9초) + 세션 간격 6.5초 ≈ **31.9초**. 사이클당 3턴이므로 1인당 **0.094 턴/초**이고, 요청은 7개(0.22 req/s)다.
- 턴 지연 1.9초 = mock 1.6초 + 인프라 약 0.3초.
- BrowseUser 1사이클 ≈ 10.6초에 요청 3개(0.28 req/s).
- 총 사용자 N명(Chat 80%) → 채팅 처리율 X = **0.0752·N 턴/초**, 총 RPS ≈ 0.232·N. T=50이면 3.8 턴/초, 약 12 RPS.

**턴당 DB 커넥션 점유 (코드 확인 결과).** `AsyncSession`은 첫 쿼리에서 커넥션을 빌리고 `commit()`까지 들고 있다.

| 구간 | pinned | routed |
|---|---|---|
| 인증·`get_chat`·사용자 메시지 저장(commit) | 점유 (수 ms) | 점유 (수 ms) |
| 도구 생성 | 쿼리 없음 → **반납 상태** | `list_all` SELECT → **점유 시작** |
| LLM 1회차 (0.8초) | 반납 상태 | **점유** |
| 검색 (`get_collection_metadata` SELECT, e5 임베딩, Qdrant) | **점유 시작** | 점유 |
| LLM 2회차 (0.8초) | **점유** | **점유** |
| 답변·usage·tool-call 로그 저장 (commit 3회) | 반납 | 반납 |
| **점유 시간** | **≈ 1.1초** | **≈ 1.9초** |

가중 평균은 (2/3)·1.1 + (1/3)·1.9 ≈ **1.37 커넥션·초/턴**이다.

| 가설 | 자원 | 턴당 비용 | 용량 | 최대 처리율 | 예상 한계 (총 사용자) |
|---|---|---|---|---|---|
| **H1** | SQLAlchemy 풀 (기본 `pool_size=5` + `max_overflow=10` = 15, `pool_timeout=30s`, [S12](https://docs.sqlalchemy.org/en/20/core/pooling.html)) | 1.37 conn·s | 15 | 10.9 턴/초 | 포화 **≈ 145**, 지연이 오르기 시작하는 지점(사용률 0.8) **≈ 115** |
| **H2** | fastembed e5-large 질의 임베딩 (API 프로세스의 CPU, `anyio.to_thread`) | 약 18 GFLOP/질의(약 0.6 GFLOP/토큰 × 약 30토큰) ≈ 호스트 전체 CPU의 60~180ms (**미측정 추정**) | 호스트 1대 | 5.5~16.7 턴/초 | **73~222** |
| H3 | 단일 uvicorn 이벤트 루프 (요청마다 `create_agent` 그래프 생성, LangChain 메시지 처리, ORM, `BaseHTTPMiddleware`) | 약 20~40ms 단일 코어 (가정) | 1코어 | 25~50 | 330~660 |
| — | Qdrant | 2회, 각 수 ms (작은 컬렉션) | 별도 컨테이너 | ≫ 50 | 먼저 막히지 않음 |
| — | Postgres `max_connections=100` | | | | 단일 프로세스(15)로는 도달하지 않는다. uvicorn 워커 7개(7×15=105)부터 문제 |
| — | Locust 클라이언트 | | 1코어 | | breakpoint 500명 ≈ 116 RPS. `HttpUser` 단일 프로세스로 충분 |

**예측.** H1과 H2는 같은 자릿수다. 어느 쪽이 먼저인지는 호스트 CPU 성능에 달렸고, 이 둘이 1차 후보다. T=50일 때 예측은 다음과 같다.

| 시나리오 | 예측 |
|---|---|
| load | 통과. H1 풀 사용률 약 34% |
| stress | 통과. 사용률 약 69% |
| spike | 3T=150에서 무릎을 넘는다. p95는 SLO를 넘지만 오류는 0이고 즉시 회복한다 |
| breakpoint | 지연 조건 L로 **약 115~150명**에서 정지 |

**폐쇄 루프 효과.** Locust 사용자는 응답을 기다린 뒤 다음 요청을 보낸다. 그래서 과부하는 먼저 지연으로 나타나고, 풀 대기가 30초를 넘어 500이 나는 시점은 훨씬 뒤다. 계산하면 ChatUser 약 443명, 총 약 550명(T=50의 11배)이다. breakpoint의 주 감지 신호가 오류율이 아니라 지연 조건 L인 이유다.

**어느 가설인지 가르는 신호** (breakpoint·spike 중에 관찰):

| 관찰 | 명령/위치 | H1 | H2 | H3 |
|---|---|---|---|---|
| 앱 DB 연결 상태 | `SELECT state, count(*) FROM pg_stat_activity WHERE datname = current_database() GROUP BY state;` | 합계가 15에 붙어 있고 `idle in transaction`이 많음 | < 15 | < 15 |
| API 프로세스 CPU | `ps -o %cpu,rss -p <uvicorn pid>` 또는 `top` | 낮음 | **≫ 100%** (ONNX가 여러 코어 사용) | **≈ 100%에서 정체** (코어 1개) |
| 백엔드 로그 | `QueuePool limit of size 5 overflow 10 reached` | 풀 대기가 30초를 넘을 때만 (폐쇄 루프라 늦게 나옴) | — | — |
| A/B | `LOADTEST_COLLECTION`을 `text-embedding-3-small` 컬렉션(mock 임베딩 50ms, CPU 사용 없음)으로 바꿔 breakpoint를 다시 실행 | 한계 변화 작음 | **한계가 크게 오름** | 변화 작음 |

A/B에 쓸 컬렉션은 백엔드와 워커가 mock을 가리키는 상태에서 인제스트해 둔다. 이때 벡터는 랜덤이라 검색 결과에 의미는 없지만, 인용은 여전히 채워진다.

**실제 LLM으로 외삽하면.** H1의 점유 시간은 LLM 지연에 비례한다. gpt-4o-mini 호출 1회를 1.5~3초로 가정하면 점유는 턴당 2.5~4.5 conn·s가 되고, 프로세스당 한계는 **약 45~80명**으로 떨어진다. mock 결과는 DB 문제를 과소평가한다. 근본 원인은 풀 크기가 아니라 LLM 호출 동안 트랜잭션을 열어 둔 채(`idle in transaction`) 커넥션을 쥐고 있는 구조다. 이 테스트의 범위 밖이므로 PM에 보고했다.

## 7. 알려진 한계

| 한계 | 영향 / 대응 |
|---|---|
| 단일 프로세스 Locust만 지원 | 시드 풀은 프로세스 메모리에 있고, breakpoint 정지 규칙은 로컬 통계를 읽는다. 분산 워커(`--processes`, `--worker`)는 지원하지 않는다. 계산상 1코어로 약 500명(116 RPS)까지 충분하다 |
| 클라이언트 CPU 포화 | Locust가 `CPU usage above 90%` 경고(`CPU_WARNING_THRESHOLD = 90`)를 내면 그 실행의 지연 수치는 클라이언트 쪽 오차다. 버린다 ([S5](https://tianpan.co/blog/2026-03-19-load-testing-llm-applications)) |
| Locust와 API를 같은 호스트에서 실행 | Locust CPU가 H2(임베딩 CPU)와 경합한다. 결과를 보고할 때 Locust CPU%를 함께 적는다 |
| mock 토큰 수는 근사 | `prompt_tokens ≈ 글자수/4`. `chat_usage_logs`·`/usage/stats`의 토큰과 비용은 의미가 없다 |
| mock은 검색 1회 후 바로 답함 | 다단계 도구 루프(재검색, 다른 도구)의 비용은 반영되지 않는다. 실제 턴은 LLM 호출이 더 많을 수 있다 |
| routed 결과는 카탈로그 순서에 의존 | mock이 첫 `- name:` 컬렉션을 고른다. 그 컬렉션의 임베딩 모델(fastembed 또는 mock)과 문서 유무에 따라 비용이 달라진다 |
| 긴 질의를 섞지 않음 | 코퍼스가 53~153자뿐이다. e5는 최대 512토큰까지 인코딩하며, 긴 입력은 짧은 질의의 약 17배 연산이 든다. 그래서 긴 프롬프트 혼합([S5](https://tianpan.co/blog/2026-03-19-load-testing-llm-applications))은 H2 최악 사례가 된다. H2가 1차 병목으로 확인되면 변형 시나리오로 추가한다 |
| 재시도 없음 | 실제 클라이언트의 재시도 폭주([S7](https://gravitee.io/corpus/gen-1448/test-management/llm-gateway-load-testing.html))는 재현하지 않는다 |
| soak 길이는 사용자가 자른다 | `-t`로 4시간보다 짧게 끊으면 누수 검출력이 떨어진다. 결과에 실제 실행 시간을 적는다 |
| 개발 DB에 데이터가 남음 | 채팅·메시지·로그 행과 `loadtest-*` 사용자가 남는다 (soak 1회에 수십만 행). 세션만 자동으로 지운다. 공유 DB에서 돌리지 않는다 |
| 인제스트 파이프라인 미포함 | 향후 시나리오 후보: 업로드 → Kafka → parser/embed/index 워커. 측정 대상은 처리량, consumer lag, `UPLOADED`→`INDEXED` 지연이다. 채팅과 별개 프로세스라 분리해서 설계한다 |

## Sources

- [S1] Grafana k6, Types of load testing — https://grafana.com/load-testing/types-of-load-testing
- [S2] Grafana k6 docs, Test types — https://grafana.com/docs/k6/next/testing-guides/test-types.md
- [S3] Salesforce Trailhead, Learn About Performance Testing Types — https://trailhead.salesforce.com/de/content/learn/modules/performance-testing-basics/learn-about-performance-testing-types
- [S4] Databricks, Load test an agent app — https://docs.databricks.com/aws/en/generative-ai/agent-framework/load-test-agent-app
- [S5] tianpan.co, Why k6 and Locust lie to you (load testing LLM applications) — https://tianpan.co/blog/2026-03-19-load-testing-llm-applications
- [S6] CallSphere, Load testing AI agent systems — https://callsphere.ai/blog/load-testing-ai-agent-systems-10000-conversations
- [S7] Gravitee, LLM gateway load testing — https://gravitee.io/corpus/gen-1448/test-management/llm-gateway-load-testing.html
- [S8] LoadForge, Load test RAG applications — https://loadforge.com/guides/ai-llm/load-test-rag-applications
- [S9] DZone, Performance testing RAG applications — https://dzone.com/articles/performance-testing-rag-applications
- [S10] Reintech, LLM load testing and benchmarking — https://reintech.io/blog/llm-load-testing-benchmark-ai-application-production
- [S11] Locust docs, Custom load shapes (`use_common_options`) — https://docs.locust.io/en/stable/custom-load-shape.html
- [S12] SQLAlchemy 2.0 docs, Connection pooling (`QueuePool` 기본값) — https://docs.sqlalchemy.org/en/20/core/pooling.html
