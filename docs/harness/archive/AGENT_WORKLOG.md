# AGENT_WORKLOG.md archive (COMPLETED tasks)

### 2026-11-14 · main-session · T-002 (사후 기록, PM이 대리 작성)
- 작업: 부하 테스트용 OpenAI 호환 mock 서버 작성 (하네스 미경유). `loadtest/pyproject.toml` 생성(`fastapi`, `locust`, `psycopg[binary]`, `uvicorn`, `package = false`) 및 `uv sync`
- 수정 파일: `loadtest/mock_openai.py`, `loadtest/pyproject.toml`, `loadtest/uv.lock` (신규)
- 산출물: 위 파일
- 검증: 메인 세션이 실제 `langchain.agents.create_agent` + `ChatOpenAI` + `AsyncOpenAI` 임베딩으로 smoke 확인 (tool_call 인자, 최종 답변, usage_metadata > 0, 3072차원) — 메인 세션 보고 기준, PM 재실행 안 함. 코드 리뷰 미실행 → T-005
- 발견한 문제: 없음
- 후속 작업: T-004에서 docstring 실행 위치 갱신, T-005 리뷰


### 2026-11-14 · system-architect · T-003
- 작업: 부하 테스트 시나리오 설계 — 사용자 모델(ChatUser 4 / BrowseUser 1, 1~5턴, 생각 시간 3~10초, pinned:routed 2:1 순번 고정), env 변수 4개, 6개 시나리오 단계표·합격 기준·breakpoint 자동 정지 규칙, SLO(채팅 턴 p95 3000ms + 내용 검증), 용량 가설(H1 DB 풀 ≈115~145명, H2 로컬 e5 임베딩 CPU ≈73~222명, H3 이벤트 루프), 한계, 출처 12개
- 수정 파일: `loadtest/SCENARIOS.md` (신규), `docs/harness/DECISION_LOG.md` (D-010 추가), `docs/harness/SYSTEM_ARCHITECTURE.md` (링크 1줄), `docs/harness/TASK_BOARD.md` (T-003 상태)
- 산출물: `loadtest/SCENARIOS.md`
- 검증: 출처 인용·URL 일치와 단계표 합계를 스크립트로 확인. Locust 동작은 `loadtest/.venv`의 locust 2.47 소스(`main.py`, `runners.py`, `stats.py`, `dispatch.py`)로 확인. DB 커넥션 점유 구간은 `agent_orchestrator.py`, `tools.py`, `retrieval_service.py`, repositories의 commit 위치로 확인. 부하 실행·e5 임베딩 실측은 미실행
- 발견한 문제: KI 등록 권한 없음 → PM에 보고: (1) LLM 호출 동안 `AsyncSession`이 트랜잭션을 열어 커넥션을 쥠(pinned는 LLM 2회차, routed는 1·2회차 모두) → 실제 LLM 지연에서 프로세스당 약 45~80명 한계 추정 (2) 기본 eval 컬렉션이 API 프로세스 CPU에서 e5-large 임베딩을 돌림 (3) `GET /collections/{name}/documents`가 컬렉션 전체 포인트를 scroll(O(포인트 수))
- 후속 작업: PM 승인 → T-004(`backend-developer`)가 SCENARIOS.md대로 locustfile 구현

### 2026-11-14 · backend-developer · T-004
- 작업: SCENARIOS.md대로 Locust 부하 테스트 구현 — ChatUser/BrowseUser, test_start 시드·test_stop 세션 삭제, 6개 시나리오 단계표 shape(`-t` 직접 적용, breakpoint 자동 정지), 내용 검증(§5 실패 메시지), quitting 합격 게이트. 작업 중 사용자 요청("task, user, core, utils 등 폴더 구조로 리팩터")에 따라 PM 지시(단일 파일) 대신 패키지 구조로 분리
- 수정 파일: `loadtest/locustfile.py`(진입점), `loadtest/core/{config,hooks}.py`, `loadtest/users/{base,chat,browse}.py`, `loadtest/tasks/{chat,browse}.py`, `loadtest/shapes/scenario.py`, `loadtest/utils/{sessions,http,validation}.py`, 각 `__init__.py`(신규), `loadtest/README.md`(신규), `loadtest/mock_openai.py`(docstring만), `.gitignore`(`loadtest/reports/` 추가)
- 산출물: 위 파일
- 검증: (1) `LOADTEST_SCENARIO=bogus`/`LOADTEST_TARGET_USERS=0` → exit 1 + 유효값 출력 (2) scratch 스크립트로 6개 시나리오 tick 표가 SCENARIOS.md T=50 단계표와 일치, breakpoint 합성 통계로 L(30초 연속)·F(창 실패율)·29초 blip 무정지 확인 (3) 실제 스택(mock + sk-mock 백엔드) smoke: 85 req, 실패 0, 채팅 턴 23건 p95 2400ms, exit 0, 종료 후 `loadtest-%` 세션 0건 (4) load T=5 `-t 90s` 90초에 정지, exit 0 (5) `LOADTEST_CHAT_P95_MS=100` smoke → 게이트 실패 exit 1 (6) `validate_turn` 가짜 응답 7케이스. ruff check/format clean (`mock_openai.py` 제외)
- 발견한 문제: SCENARIOS.md §4 근거 중 "start()가 램프 동안 막힘"은 LocalRunner에는 해당 안 됨(2.47 `LocalRunner.start`는 spawn 그린렛을 띄우고 즉시 반환, 다음 tick에 진행 중 spawn을 kill) — 설계(보간 목표 + 고정 rate)는 그대로 유효, 문서 근거만 부정확 → architect 보고. `mock_openai.py` ruff FURB167(`re.M`) → T-005
- 후속 작업: T-005 리뷰(패키지 구조 포함), SCENARIOS.md "locustfile.py가 구현" 문구·§4 근거 갱신 여부 architect 판단

### 2026-11-14 · system-architect · T-006
- 작업: SCENARIOS.md와 D-010(e)의 잘못된 램프 근거("start()가 램프 동안 tick을 막음") 정정, 패키지 구조 반영, §5 실패 메시지 표 보강
- 수정 파일: `loadtest/SCENARIOS.md` (3행 레이아웃 참조, §4 공통 규칙 spawn rate 항목, §5 품질 관문 표), `docs/harness/DECISION_LOG.md` (D-010 상태줄, D-011 추가), `docs/harness/TASK_BOARD.md` (T-006 행)
- 산출물: 위 문서 수정
- 검증: `loadtest/.venv`의 locust 2.47 소스 확인. `LocalRunner.start`(runners.py:550-564)는 진행 중인 spawn greenlet을 kill하고 새로 spawn한 뒤 반환. `MasterRunner.start`는 dispatcher를 그 자리에서 돌고, dispatcher가 `gevent.sleep`(dispatch.py:298)하므로 master에서만 블로킹. §5 순서는 `utils/validation.py`(non-mock 검사가 인용 검사보다 먼저), `empty chat id`는 `tasks/chat.py:61-64`와 호출부 :34-35(None이면 턴 안 보냄)로 확인. 부하 실행은 하지 않음
- 발견한 문제: 없음. D-010(c)의 "단일 스크립트 도구" 표현이 낡은 점은 D-011 참고란에 적음
- 후속 작업: PM 확인 후 COMPLETED

### 2026-11-14 · backend-code-reviewer · T-005
- 작업: T-002(`mock_openai.py`) + T-004(loadtest 패키지·README) 코드 리뷰 → CR-001 **CHANGES_REQUESTED**
- 수정 파일: `docs/harness/CODE_REVIEW_LOG.md` (CR-001), `docs/harness/KNOWN_ISSUES.md` (KI-013), `docs/harness/TASK_BOARD.md` (T-002·T-004 → REVISION_REQUIRED, T-005 → BLOCKED). 코드 수정 없음
- 산출물: CR-001 (Major 2, Minor 7)
- 검증: `uvx ruff check`/`format --check` (mock_openai.py 실패), 인프라 DOWN 상태에서 시드 실패 재현(load exit 0), scratch locustfile로 시드-tick kill 경합 시뮬레이션(시드 10회 시작·0회 완료, exit 0), psycopg gevent 대기 함수 확인(`wait_poll`), `u()` 반올림 전수 비교, 단계 경계 tick 값, mock을 실제 `ChatOpenAI`/`AsyncOpenAI`로 호출(pinned·routed·도구 없음·stream·임베딩 차원), mock 임베딩 직렬화 비용 측정. 실제 스택 실행 안 함(인프라 DOWN)
- 발견한 문제: (1) 시드 실패나 채팅 0턴이어도 load/stress/soak 게이트가 exit 0 (2) 협조적 psycopg 시드가 tick 변화 시 `LocalRunner.start`에 kill돼 무한 재시드 → 사용자 0명, breakpoint T 크게 하면 발생 (3) Minor: onset 잔존, json 예외 미집계, 정리 실패 무시, README 종료 코드, mock ruff/docstring/base64(KI-013)
- 후속 작업: `backend-developer`가 CR-001 #1~#8 수정 → CR-002 재리뷰

### 2026-11-14 · backend-developer · T-004 + T-002 (CR-001 수정)
- 작업: CR-001 #1~#8 수정. (1) 시드 실패·세션 삭제 실패 시 `process_exit_code = 1`, 모든 게이트 시나리오에 `chat_turns=0`·`runner.exceptions` 실패 사유 추가 (2) shape는 시드가 끝날 때까지(세션 풀이 비었거나 runner 상태가 INIT) `(0, SPAWN_RATE)`를 반환하고 `reset_time()`. 첫 tick은 `shape_last_tick=None`과 달라 `start()` → `_start` → `test_start`를 한 번 일으키고, 같은 tick이 이어지니 kill이 없다. 0명 `_start`가 끝나면 `spawning_complete`로 RUNNING이 돼 이후 `start()`는 `test_start`를 다시 쏘지 않는다(locust 2.47 runners.py:342-377, 469-489, 136-139 확인). 시드 왕복을 2N → 2로 줄임(generate_series upsert + unnest insert) (3) onset 초기화 (4) `response.json()` ValueError → `invalid json` (5) README 종료 코드·`-t` 기준·selfcheck 줄 (6) mock ruff·docstring. `loadtest/selfcheck.py` 추가
- 수정 파일: `loadtest/core/hooks.py`, `loadtest/shapes/scenario.py`, `loadtest/utils/{sessions,validation}.py`, `loadtest/tasks/chat.py`, `loadtest/mock_openai.py`, `loadtest/README.md`, `loadtest/selfcheck.py`(신규), `docs/harness/TASK_BOARD.md`(T-002·T-004 행)
- 산출물: 위 파일
- 검증: `uvx ruff check --exclude .venv .` All checks passed, `uvx ruff format --check --exclude .venv .` 21 files already formatted. `uv run python selfcheck.py` → selfcheck OK. 시드 게이트·onset 초기화·invalid json 수정을 하나씩 되돌리면 selfcheck가 각각 실패함을 확인. 인프라 DOWN에서 `LOADTEST_SCENARIO={load,spike,smoke} LOADTEST_TARGET_USERS=2 ... --host http://127.0.0.1:1 -t 8s --only-summary` → 모두 exit 1(load: "시드 실패" + "합격 게이트 실패: chat_turns=0"). 리뷰어 race_locustfile(breakpoint T=500, 시드 2.5초, -t 10s) → 시드 시작 1회·완료 1회, 0→3→6… 램프, 총 12.4초. 실제 스택(mock + sk-mock 백엔드) smoke `--csv reports/smoke` → 94 req, 실패 0, 채팅 21턴 p95 2300ms, exit 0, 시드 3/삭제 3, 잔여 loadtest 세션 0. 종료 후 Docker down, 5432/8000/9000 닫힘(시작 전 상태와 같음)
- 발견한 문제: SCENARIOS.md가 `-t`/유예 기준 시각을 "테스트 시작"으로 읽힐 수 있음 → 시드 완료 기준으로 바뀜, 문구 수정은 architect에 보고(PM 경유)
- 후속 작업: T-005 CR-002 재리뷰

### 2026-11-14 · system-architect · T-007
- 작업: SCENARIOS.md §4 공통 규칙·§4.6 유예 문구를 CR-001 #2 수정(시드 완료 전 `(0, 100)` + `reset_time()`, 시계는 시드 완료부터)에 맞춤
- 수정 파일: `loadtest/SCENARIOS.md` (§4 공통 규칙에 시드 대기 항목 1개 추가, `-t` 항목에 시계 기준 2문장 추가, §4.6 유예 항목에 괄호 1개), `docs/harness/TASK_BOARD.md` (T-007 행)
- 산출물: 위 문서 수정
- 검증: `loadtest/shapes/scenario.py:75-80`(`has_sessions()`/`STATE_INIT` 가드, `reset_time()`, `return 0, SPAWN_RATE`), `utils/sessions.py:43-64`(왕복 2회) 소스 확인. §3 인증 우회(48행 "test_start, 첫 사용자 spawn 전")·§7은 코드와 모순 없어 수정 안 함. 부하 실행은 하지 않음
- 발견한 문제: 없음. D-010/D-011 범위 내 구현 설명이라 DECISION_LOG 항목은 추가하지 않음
- 후속 작업: PM 확인 후 COMPLETED

### 2026-11-14 · backend-code-reviewer · T-005 (CR-002 재리뷰)
- 작업: CR-001 #1~#8 수정분 재리뷰 및 #2 수정의 회귀 점검(시드 실패 quit, web UI 재실행 상태, reset_time·deque 상호작용, 시드 SQL)
- 수정 파일: `docs/harness/CODE_REVIEW_LOG.md` (CR-002 추가, CR-001 재리뷰 줄 갱신), `docs/harness/KNOWN_ISSUES.md` (KI-014), `docs/harness/TASK_BOARD.md` (T-005 COMPLETED, T-002/T-004 검증 칸에 리뷰 통과)
- 산출물: CR-002 PASS_WITH_NOTES
- 검증: 인프라 DOWN 확인 후 `uvx ruff check/format --check` clean, `uv run python selfcheck.py` OK, DB 없이 load/spike/smoke `-t 8s` 모두 exit 1, 시드 경합 재현(breakpoint T=500) 시드 1회 후 램프, 시드 20초 정지 변형 `-t 5s` → 25초, selfcheck 되돌리기 5종 모두 실패 후 원본 복원(`shasum -c` OK)
- 발견한 문제: KI-014 (시드 타임아웃 없음 → `-t` 무한 지연, Minor)
- 후속 작업: PM이 T-002/T-004 완료 처리. KI-014는 backend-developer 선택 수정

### 2026-11-14 · pm · T-002~T-007
- 작업: FR-009 부하 테스트 환경 오케스트레이션. T2 분류, architect(설계 T-003, 정정 T-006/T-007) → backend-developer(T-004 + 수정) → backend-code-reviewer(CR-001 CHANGES_REQUESTED → CR-002 PASS_WITH_NOTES)
- 수정 파일: docs/harness/{REQUIREMENTS,TASK_BOARD,KNOWN_ISSUES(KI-010~012 등록),AGENT_WORKLOG}.md, CLAUDE.md (loadtest 항목)
- 산출물: loadtest/ (SCENARIOS.md, README.md, locustfile.py + core/shapes/users/tasks/utils, selfcheck.py, mock_openai.py)
- 검증: PM 재실행 — `uvx ruff check --exclude .venv .` → All checks passed, `uvx ruff format --check` → 21 files formatted, `uv run python selfcheck.py` → OK, `LOADTEST_SCENARIO=bogus`/`LOADTEST_TARGET_USERS=0` → exit 1, 단계표 T=50 문서 대조 일치, Locust 소스(main.py:571/580, runners.py:550-563) 확인. 실스택 smoke는 개발자 실행 결과(94 req/0 fail/p95 2300ms/exit 0) 수용, PM 재실행 안 함
- 발견한 문제: KI-010~014. 개발자가 "사용자가 직접 패키지 구조 리팩터를 요청했다"고 보고 — PM은 해당 사용자 메시지를 확인하지 못함, 호출자에게 확인 요청
- 후속 작업: KI-014(시드 타임아웃) 1줄 수정 선택, KI-010 측정(stress/breakpoint 실행)

### 2026-11-14 · system-architect · T-008
- 작업: 로컬 모니터링 스택 설계 (별도 compose 프로젝트, 외부 네트워크 `rag_chatbot_default`, exporter·이미지 버전·Qdrant Bearer credentials_file 방식, 백엔드 /metrics는 후속)
- 수정 파일: `docs/harness/DECISION_LOG.md` (D-012)
- 산출물: D-012 (PM이 Accepted 처리)
- 검증: `docker compose config`로 네트워크 이름 확인 (보고 기준). 이미지 태그 pull 검증은 미실행 (Docker 데몬 정지)
- 발견한 문제: Kafka `:latest`(4.x 추정)와 exporter `--kafka.version` 불일치 가능, Docker Desktop에서 cAdvisor 컨테이너 이름 누락 가능
- 후속 작업: T-009 구현

### 2026-11-14 · backend-developer · T-009
- 작업: 모니터링 스택 구현 (D-012): prometheus, grafana(데이터소스 프로비저닝), postgres/redis/kafka exporter, cadvisor, qdrant 직접 스크레이프
- 수정 파일: `monitoring-docker-compose.yaml`, `monitoring/prometheus/prometheus.yml`, `monitoring/grafana/provisioning/datasources/prometheus.yml`, `docs/ARCHITECTURE.md` (Monitoring 섹션)
- 산출물: 위 파일
- 검증: `docker compose -f monitoring-docker-compose.yaml config` exit 0, docker.env 비밀값 grep 0건 (보고 기준, compose config는 PM 재실행 확인). promtool·이미지 태그·postgres-exporter `/bin/sh` 존재 여부 미실행 (Docker 데몬 정지)
- 발견한 문제: Grafana 기본 admin/admin, 네트워크 이름은 디렉터리명 기반 가정
- 후속 작업: T-010 리뷰

### 2026-11-14 · backend-code-reviewer · T-010
- 작업: T-009 정적 리뷰 (CR-003 PASS_WITH_NOTES)
- 수정 파일: `docs/harness/CODE_REVIEW_LOG.md`, `docs/harness/KNOWN_ISSUES.md`
- 산출물: CR-003, KI-015(0.0.0.0 바인딩 + Grafana admin/admin, Major), KI-016(env_file 전체 비밀 노출, Minor), KI-017(kafka-exporter vs Kafka 4.x, Minor)
- 검증: 정적 판독만. promtool·이미지 pull·스택 기동 미실행 (Docker 데몬 정지)
- 발견한 문제: 위 KI + 빈 Qdrant 키 가드 없음, cadvisor 이름 누락 가능, postgres-exporter 슈퍼유저 접속
- 후속 작업: T-009 revision (KI-015, 키 가드)

### 2026-11-14 · backend-developer · T-009 (revision, CR-003)
- 작업: prometheus/grafana 호스트 포트 127.0.0.1 바인딩(KI-015), Qdrant 키 빈 값 fail-fast 가드
- 수정 파일: `monitoring-docker-compose.yaml`
- 산출물: 위 파일
- 검증: `docker compose -f monitoring-docker-compose.yaml config` exit 0, 렌더 결과에 host_ip 127.0.0.1·가드 존재 (보고 기준). 스택 기동 미실행
- 발견한 문제: 없음
- 후속 작업: T-013에서 재리뷰

### 2026-11-14 · frontend-code-reviewer · T-014
- 작업: T-012 정적 리뷰 (CR-004 PASS_WITH_NOTES)
- 수정 파일: `docs/harness/CODE_REVIEW_LOG.md`, `docs/harness/KNOWN_ISSUES.md`
- 산출물: CR-004, KI-018(nginx 기동 시 api DNS 고정 해석, Major), KI-019(업로드 크기 상한 근거 없음/413 HTML, Minor)
- 검증: 정적 판독만. docker build·nginx -t 미실행
- 발견한 문제: gzip 없음, HEALTHCHECK 없음 (Minor)
- 후속 작업: KI-018은 T-011과 함께

### 2026-11-14 · backend-code-reviewer · T-013
- 작업: T-015 + T-009 revision 리뷰 (CR-005 PASS_WITH_NOTES)
- 수정 파일: `docs/harness/CODE_REVIEW_LOG.md`, `docs/harness/KNOWN_ISSUES.md`
- 산출물: CR-005, KI-015 PARTIAL·Minor로 하향, KI-020, KI-021
- 검증: 설치된 instrumentator 8.1.0 소스 판독, `test_model_registry.py` 변경 stash 상태 재실행(기존 실패 확인). 전체 스위트·Docker 미실행
- 발견한 문제: 호스트 uvicorn 기본 바인딩 127.0.0.1 → Linux에서 api 타깃 DOWN 가능, 제외 경로 테스트 없음
- 후속 작업: 사용자 재개 T-015 추가 변경분 재리뷰
### 2026-11-14 · backend-developer · T-015
- 작업: FastAPI `/metrics` (prometheus-fastapi-instrumentator 8.1.0), API 호출 로그 제외 경로에 추가, prometheus `api` 잡(host.docker.internal:8000) + extra_hosts
- 수정 파일: `backend/app/main.py`, `backend/app/core/constants.py`, `backend/app/pyproject.toml`, `backend/app/uv.lock`, `backend/tests/test_main.py`(신규), `monitoring/prometheus/prometheus.yml`, `monitoring-docker-compose.yaml`, `docs/ARCHITECTURE.md`
- 산출물: 위 파일
- 검증: 신규 테스트 통과(red→green), 전체 93 passed / 2 failed(기존 `test_model_registry.py`), ruff clean, monitoring compose config exit 0 — PM 재실행으로 테스트·ruff 확인
- 발견한 문제: `/metrics` 무인증(nginx가 /api/만 프록시하는 동안만 안전), 기존 테스트 실패 2건
- 후속 작업: T-013 리뷰


### 2026-11-14 · backend-developer · T-015 (사용자 직접 재개 추가분)
- 작업: `LOG_INFRA_ENDPOINTS`(기본 false) — /health·/metrics를 API 호출 로그와 uvicorn.access 로그에서 제외
- 수정 파일: `backend/app/core/config.py`, `core/constants.py`, `core/logging_config.py`, `middlewares/api_call_log_middleware.py`, `backend/tests/core/test_logging_config.py`, `backend/tests/middlewares/test_api_call_log_middleware.py`, `docs/ARCHITECTURE.md`
- 산출물: 위 파일
- 검증: 신규 테스트 red→green, 전체 100 passed / 2 failed(기존), ruff clean — PM 재실행 확인. 실서버 로그 관찰 미실행
- 발견한 문제: `.env.example` 없음 → 새 env 변수 템플릿 미기재
- 후속 작업: T-017 재리뷰

### 2026-11-14 · backend-code-reviewer · T-017
- 작업: T-015 추가분 재리뷰 (CR-006 PASS_WITH_NOTES)
- 수정 파일: `docs/harness/CODE_REVIEW_LOG.md`
- 산출물: CR-006
- 검증: `pytest -k "logging_config or api_call_log"` 19 passed, uvicorn 0.49.0 소스 대조. 실서버 미실행
- 발견한 문제: `/`도 uvicorn access 로그에서 제외(의도 확인 필요), 음성 케이스 테스트 없음 (Minor)
- 후속 작업: 없음
### 2026-11-14 · backend-developer · T-018
- 작업: Loki 3.6.7(파일시스템, 7일 보존) + Alloy v1.12.2(docker.sock 기반 컨테이너 로그 수집) + Grafana Loki 데이터소스 + prometheus loki/alloy 잡
- 수정 파일: `monitoring-docker-compose.yaml`, `monitoring/loki/loki-config.yaml`, `monitoring/alloy/config.alloy`, `monitoring/grafana/provisioning/datasources/loki.yml`, `monitoring/prometheus/prometheus.yml`, `docs/ARCHITECTURE.md`
- 산출물: 위 파일
- 검증: monitoring compose config exit 0 (PM 재실행 확인). loki -verify-config·alloy fmt 미실행 (Docker 데몬 정지)
- 발견한 문제: Alloy가 docker.sock 접근(사실상 root, 로컬 전용)
- 후속 작업: T-019 리뷰

### 2026-11-14 · backend-code-reviewer · T-019
- 작업: T-018 리뷰 (CR-007 PASS_WITH_NOTES)
- 수정 파일: `docs/harness/CODE_REVIEW_LOG.md`, `docs/harness/KNOWN_ISSUES.md`
- 산출물: CR-007, KI-022
- 검증: 정적 판독 + context7(Loki). loki -verify-config·alloy fmt·기동 미실행
- 발견한 문제: Alloy 상태 볼륨 없음, Loki analytics 기본 on, Loki 데이터소스 uid 미고정 (모두 Minor)
- 후속 작업: 없음
### 2026-11-14 · frontend-code-reviewer · T-023
- 작업: T-021 리뷰 (CR-008 PASS_WITH_NOTES)
- 수정 파일: `docs/harness/CODE_REVIEW_LOG.md`, `docs/harness/KNOWN_ISSUES.md` (KI-018 RESOLVED)
- 산출물: CR-008
- 검증: 정적 판독. nginx -t·런타임 미실행
- 발견한 문제: api 부재 시 첫 요청 502 (Minor, 수용)
- 후속 작업: Docker 기동 후 smoke

### 2026-11-14 · backend-code-reviewer · T-022
- 작업: T-020 리뷰 (CR-009 PASS_WITH_NOTES)
- 수정 파일: `docs/harness/CODE_REVIEW_LOG.md`
- 산출물: CR-009
- 검증: 정적 판독(alembic 경로·쓰기 경로·env override·.dockerignore). 빌드·기동 미실행
- 발견한 문제: WorkerImage.Dockerfile:3-4 주석 부정확(/app 소스는 미컴파일), api healthcheck 없음 (Minor)
- 후속 작업: Docker 기동 후 smoke
### 2026-11-14 · backend-code-reviewer · T-024
- 작업: T-020 revision 리뷰 (CR-010 PASS_WITH_NOTES)
- 수정 파일: `docs/harness/CODE_REVIEW_LOG.md`
- 산출물: CR-010
- 검증: 정적 판독. 이미지 빌드 미실행
- 발견한 문제: compileall이 .venv까지 순회 → 의도적 문법 오류 파일 있으면 빌드 실패 가능 (Minor)
- 후속 작업: 첫 빌드 결과 확인
### 2026-11-14 · pm · T-025
- Work: harness upkeep (user items 1, 2, 3, 5, 6, 7, 8, 9): version the harness in git (D-014), §2 as the single ownership source, `tools:` allowlists for 9 agents, infra-config rules, `VERIFY_BLOCKED`, latest-only board cells, agent-facing docs in English, `Cost:` line in the worklog format
- Files: `.gitignore`, `CLAUDE.md`, `.claude/agents/*.md`, `.claude/.rules/*.md`, `docs/harness/*.md`, `docs/harness/archive_logs.py`
- Deliverables: the files above
- Verification: `python3 docs/harness/archive_logs.py --dry-run` (see the T-025 board row); secret scan of newly tracked files: no hits. Subagent behavior with the new `tools:` lists not run (main session measures on the next real spawn)
- Issues found: none
- Follow-up: on the next spawn, confirm the allowlists don't strip anything a subagent needs (e.g. the hand-back tool)
- Cost: n/a (no subagent)
### 2026-11-14 · qa-engineer · T-026
- Work: fresh infra up, `rag_eval_papers` ingested (3 PDFs, mock env), Locust smoke then load (T=50, 35 min) against host uvicorn + mock OpenAI
- Files: `loadtest/RESULTS.md` (new), `docs/harness/QA_REPORT.md` (QA-001), `docs/harness/KNOWN_ISSUES.md` (KI-023, KI-024)
- Deliverables: `loadtest/RESULTS.md`
- Verification: smoke exit 0 (92 req, 0 fail, chat p95 2300 ms); load exit 1 (22,367 req, 9 fail, 10.65 RPS, chat p50 1900 / p95 3900 ms > 3000 gate). No real OpenAI call. Prometheus not run
- Issues found: KI-023 (5 stall windows push chat p95 over gate; cause unproven, embedding-in-API suspected, KI-011), KI-024 (9 `http 0` failures)
- Follow-up: decide rerun with Locust on another machine vs `system-architect` on embedding offload
- Cost: 128,545 tokens / 51 tool uses / 3,329 s
### 2026-11-21 · rag-llm-engineer · T-027
- Work: run eval baseline, add results export to eval/
- Files: `eval/src/results-reporter.ts` (new), `eval/playwright.config.ts`, `eval/src/{types,db}.ts`, `eval/tests/rag-eval.spec.ts`, `eval/README.md`, `eval/results/2026-11-21-baseline-r{1,2}.{json,md}`
- Verification: 2 live runs; 0/9 pass (golden expectedDocumentIds stale after 2026-11-14 re-ingest), judge 0.911/0.944, mean tokens 8344/8082, p95 10840/11223 ms. PM re-ran `npx tsc --noEmit` OK
- Issues found: stale golden ids; scores don't separate hit/miss (KI-004 cutoff won't help); 300-char snippets cause repeated searches (`tools.py:23,34`); 4/9 cases answer without tools yet judge scores high; afterAll `console.table` prints only last case
- Follow-up: T-028
- Cost: 120378 tokens, 42 tool uses, 541 s

### 2026-11-21 · rag-llm-scientist · T-028
- Work: diagnose retriever/embedding/agent quality from T-027 evidence + code + offline probe; write improvement plan
- Files: `docs/RAG_IMPROVEMENT_PLAN.md` (new). PM added `eval/results/2026-11-21-probe/{probe,tok}.py` (scratchpad copy, key → env var) and fixed stale chunk counts in `eval/README.md`
- Verification: offline probe reproduced live `query_points` top-8 on 72/72 (as reported); n=9, unreviewed regex labels → directional only. No eval runs
- Issues found: KI-025..KI-029 (stale golden ids, judge blind to grounding, e5 512-token truncation, 300-char snippets, BM25 hurts Korean hybrid); GPT paper never says "GPT" so BERT outranks it
- Follow-up: plan §4 experiment order, starting with eval fixes E1-E6
- Cost: 113359 tokens, 41 tool uses, 897 s
