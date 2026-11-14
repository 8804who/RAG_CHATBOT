# CODE_REVIEW_LOG.md archive (COMPLETED tasks)

### CR-001 · 2026-11-14 · backend-code-reviewer · T-005 (T-002 + T-004)
- 리뷰 대상: `loadtest/` 미커밋 전체 — `locustfile.py`, `core/{config,hooks}.py`, `shapes/scenario.py`, `users/{base,chat,browse}.py`, `tasks/{chat,browse}.py`, `utils/{sessions,http,validation}.py`, `mock_openai.py`, `README.md` (SCENARIOS.md·D-010 대조, locust 2.47 / psycopg 3.3.9 / openai SDK 설치 소스 대조)
- 결과: **CHANGES_REQUESTED** (T-004: Major 2건. T-002: Minor만 있으나 ruff 게이트 실패)
- 검증 (인프라 DOWN, 5432/8000/9000 닫힘 확인 후 실행):
  - `uvx ruff check --exclude .venv .` → FURB167 1건 (`mock_openai.py:42`), exit 1
  - `uvx ruff format --check --exclude .venv .` → `mock_openai.py` 1개 파일 reformat 필요 (19개 clean), exit 1
  - 시드 실패 재현: `LOADTEST_SCENARIO={load,spike,smoke} LOADTEST_TARGET_USERS=2 uv run locust -f locustfile.py --headless --host http://127.0.0.1:1 -t 8s` → load **exit 0** ("합격 게이트 통과: chat_turns=0"), spike exit 1 (ZeroDivisionError 예외 때문), smoke exit 1
  - 시드-tick 경합 시뮬레이션: scratch locustfile이 `core.hooks.seed_sessions`를 `gevent.sleep(2.5)`로 바꿔 `LOADTEST_SCENARIO=breakpoint LOADTEST_TARGET_USERS=500 -t 10s` → 시드 시작 10회·완료 0회, 사용자 0명, exit 0
  - `import locust` 후 `psycopg.waiting.wait.__name__` → `wait_poll` (gevent 패치 감지 → 협조적 대기). locust 없이는 `wait_c`
  - `u()` 반올림: x∈{0.3,1,2,3,10}, T=1..5000에서 float ceil vs Fraction ceil 불일치 0건
  - 단계 경계 tick 값 (T=50, 5개 시나리오): SCENARIOS.md 단계표와 일치
  - mock(:9123)에 backend venv의 `ChatOpenAI.bind_tools`/`AsyncOpenAI.embeddings`로 호출: pinned·routed tool_call(routed는 `collection_name='rag_eval_papers'` 파싱), ToolMessage 후 `[mock]` 답변, 도구 없음 → 답변, usage_metadata 채워짐, 임베딩 1536/3072차원 float, `stream=True` → 400
  - mock 임베딩 응답 생성+직렬화 비용: 3072차원 2.23ms, 1536차원 1.11ms/호출 (응답 64KB/32KB)

**T-004 (locust 패키지)**

| # | 심각도 | 위치 (file:line) | 문제 | 수정 요청 | 신뢰도 | 처리 |
|---|---|---|---|---|---|---|
| 1 | Major | `core/hooks.py:34-40`, `:75-92` | 시드 실패 시 `process_exit_code`를 안 정하고, load/stress/soak 게이트는 채팅 턴 0건이어도 통과해 `process_exit_code = 0`으로 덮어씀 → DB가 꺼진 채 load를 돌리면 exit 0. 게이트가 0을 박아서 Locust의 다른 비정상 신호(`runner.exceptions`, test_stop 핸들러 예외로 켜지는 `unhandled_greenlet_exception`)도 묻힘 | 시드 except에서 `environment.process_exit_code = 1`. 모든 게이트 시나리오에 `chat.num_requests == 0`이면 실패 사유 추가. `environment.runner.exceptions`가 있으면 실패 사유 추가 | confirmed (재현) | 미처리 |
| 2 | Major | `core/hooks.py:26-41` + `utils/sessions.py:44-59` + `shapes/scenario.py:66-89` | 시드는 spawn 그린렛 안의 `test_start`에서 돈다. locust가 gevent를 패치해서 psycopg가 DB 왕복마다 양보한다. 그 사이 tick 값이 바뀌면 `LocalRunner.start`(runners.py:559-561)가 그 그린렛을 kill한다. 상태가 아직 INIT이라 다음 `_start`가 `test_start`를 다시 쏘고, 시드는 처음부터 다시 시작한다. 시드가 tick 값 변화 간격보다 오래 걸리면 끝나지 않는다: 사용자 0명, 오류 0, exit 0. breakpoint는 30분 뒤 "no breakpoint up to 10×T"를 남겨 T를 더 올리라고 유도한다. 시드는 2N회 왕복(N=10T)이고 첫 tick 변화는 180/T초 뒤에 온다 → 왕복 0.3~1ms 기준 breakpoint T≳100~175에서 발생. SCENARIOS §4.6-6의 "T를 올려 재실행" 경로다 | 시드가 끝날 때까지 shape가 `(0, SPAWN_RATE)`를 반환하고 매 tick `self.reset_time()`(같은 tick이면 `start()` 재호출 없음 → kill 없음, 램프 시계는 시드 완료부터). 보조로 `executemany`(pipeline)로 시드 왕복을 줄인다 | confirmed (메커니즘, 시뮬레이션) / plausible (실제 임계 T) | 미처리 |
| 3 | Minor | `shapes/scenario.py:130-134` | streak가 0으로 돌아가도 `_onset_users`를 지우지 않음 → reason=errors 정지 로그에 이전에 끊긴 지연 streak의 onset이 남음 | `self._streak = 0` 옆에 `self._onset_users = None` | confirmed (코드 판독) | 미처리 |
| 4 | Minor | `utils/validation.py:22`, `tasks/chat.py:61` | `catch_response` 블록 안에서 `response.json()`이 실패하면 `ResponseContextManager.__exit__`(clients.py:398-404)가 요청을 통계에 넣지 않고 예외를 올려보낸다 → 실패율에 안 잡힘 (#1 때문에 게이트도 못 봄) | `try: body = response.json() except ValueError: response.failure("invalid json"); return ...` | confirmed (Locust 소스) / 발생 가능성 낮음 | 미처리 |
| 5 | Minor | `core/hooks.py:52` | `delete_sessions()` 예외(종료 시 DB 다운)는 EventHook이 로그만 남김. 이어서 게이트가 exit 0을 박아서 세션이 남아도 성공으로 끝남 (24h 만료로 피해는 작음) | try/except → `logger.exception` + `process_exit_code = 1` | confirmed (코드 판독: event.py:44-52, main.py:637-645) | 미처리 |
| 6 | Minor | `README.md:32` | spike/breakpoint의 종료 코드가 문서에 없다. Locust 기본값으로 실패가 1건만 있어도 1이 된다(`exit_code_on_error`). spike는 급증 구간 오류를 "기록만" 하므로 대부분 1로 끝난다 | 한 줄 추가: spike/breakpoint는 exit code를 합격 판정에 쓰지 않음 | confirmed (main.py:640-645) | 미처리 |

**T-002 (`mock_openai.py`)**

| # | 심각도 | 위치 (file:line) | 문제 | 수정 요청 | 신뢰도 | 처리 |
|---|---|---|---|---|---|---|
| 7 | Minor | `mock_openai.py:42`, `:74`, `:86`, `:106` | ruff FURB167(`re.M`) + ruff format 불일치 | `uvx ruff check --fix` + `uvx ruff format` | confirmed | 미처리 |
| 8 | Minor | `mock_openai.py:34`, `:38`, `:48`, `:97` | D-010(c)의 docstring 형식(한국어 명사형 요약 + Parameters/Returns) 미준수: 3개 함수는 docstring 없음, `_search_args`는 Parameters/Returns 없음 | 형식 맞춰 추가 | confirmed | 미처리 |
| 9 | Minor | `mock_openai.py:96-110` | openai SDK는 `encoding_format`이 없으면 `base64`를 요청한다(embeddings.py:110). mock은 float 배열 JSON을 돌려준다. SDK가 받아주기는 한다(`_parsing/_embeddings.py`). 다만 백엔드가 질의마다 32~64KB JSON과 float 1536~3072개를 파싱하게 되고, 실제 OpenAI라면 base64 8~16KB만 받는다. 그래서 H2 A/B 팔(CPU 측정)에 실제로 없는 백엔드 CPU가 조금 얹힌다 | `encoding_format == "base64"`면 `base64.b64encode(array("f", vec).tobytes())` 반환 | confirmed (동작) / plausible (영향 크기) | KI-013 |

확인했고 문제 없는 항목:
- 과금: README·mock docstring 모두 `OPENAI_BASE_URL`+`sk-mock`. 백엔드는 `ChatOpenAI(api_key=config...)`/`AsyncOpenAI(api_key=...)`에 base_url을 넘기지 않아 env를 따른다. pydantic-settings에서 셸 env가 `.env`보다 우선한다. `[mock]` 검사는 인용 검사보다 먼저이고, non-200·빈 content 뒤에 온다. `process_exit_code = 1`을 정한 뒤 quit하고 게이트는 1을 덮어쓰지 않는다. quit가 여러 번 불려도 무해하다(stop은 STOPPED면 반환)
- 정리: 정상 종료·`-t`(shape → `quit`)·Ctrl-C(main.py:572-575 finally → quit)·SIGTERM(shutdown → `runner.quit`)·non-mock·게이트 실패 모두 `test_stop`을 거친다. 삭제는 이번 실행 토큰만 `token = ANY(%s)`로 지운다. 시드 실패나 kill 시에는 `with conn`이 롤백해서 남는 행이 없다. SQL은 전부 파라미터화되어 있다. 토큰·비밀번호는 로그에 안 나온다(재현 로그의 psycopg 오류에는 host/port만 있음)
- shape: 보간·`ceil`·`u()`·`-t` 상한·종료 `None`이 SCENARIOS.md와 일치한다. breakpoint는 유예 중에도 스냅샷을 쌓는다. deque(61)[0]은 60초 창이고, [-11]은 10초 Δreq다. 엔트리는 매 tick 이름으로 다시 조회하므로 `clear_all` 뒤에도 오래된 참조가 없다. `get_current_response_time_percentile`은 로컬 기본 `use_response_times_cache=True`(stats.py:213)
- 사용자: pinned/routed `n % 3 == 1`, 실패 메시지, `name=` 그룹, 모든 요청 timeout 60초가 §2·§5와 일치한다. `itertools.count`는 yield 없이 원자적이다. psycopg는 gevent 패치 상태에서 협조적으로 돈다. 시드와 정리는 사용자가 없을 때만 돌아서, #2를 빼면 블로킹 여부는 결과에 영향이 없다
- 패키지 구조: 순환 import 없음. site-packages에 `core/utils/tasks/users/shapes` 이름 충돌 없음. import 부작용은 `core/config.py`의 env 검증 `sys.exit`과 `core/hooks.py`의 리스너 등록뿐이고 둘 다 의도된 것이다
- mock: 이번 턴 메시지만 보면 된다(오케스트레이터가 히스토리 없이 현재 query만 보냄, `agent_orchestrator.py:184`). routed 정규식은 `tools.py:79` 형식과 맞는다. 카탈로그가 비면 `""`를 보내고 이어서 답한다. 병목도 아니다: 임베딩 2.2ms, chat <0.1ms 연산. 설계 규모(약 37턴/초)에서 코어 10% 미만
- 재리뷰: CR-002 (PASS_WITH_NOTES)

### CR-002 · 2026-11-14 · backend-code-reviewer · T-005 재리뷰 (T-002 + T-004, CR-001 수정분)
- 리뷰 대상: `loadtest/core/hooks.py`, `shapes/scenario.py`, `utils/{sessions,validation}.py`, `tasks/chat.py`, `mock_openai.py`, `README.md`, 신규 `selfcheck.py`. locust 2.47 설치 소스(`runners.py` 336-341·342-379·381-421·470-499, `main.py` 567-582, `shape.py` 37-49)와 백엔드 `models/{user,session}.py` 컬럼 타입 대조
- 결과: **PASS_WITH_NOTES** (CR-001 #1~#8 모두 해결, 새 Minor 1건 → KI-014)
- 검증 (인프라 DOWN: 5432/8000/9123 닫힘 확인, `unset VIRTUAL_ENV`, `loadtest/`에서 실행):
  - `uvx ruff check --exclude .venv .` → All checks passed. `uvx ruff format --check --exclude .venv .` → 21 files already formatted
  - `uv run python selfcheck.py` → selfcheck OK
  - DB 없이 `LOADTEST_SCENARIO={load,spike,smoke} LOADTEST_TARGET_USERS=2 uv run locust -f locustfile.py --headless --host http://127.0.0.1:1 -t 8s` → 3개 모두 **exit 1**. 시드 실패 로그 → test_stop(sessions=0) → quitting 게이트("chat_turns=0") 순서로 실행됨. spike는 게이트 없이 시드 except의 exit 1
  - CR-001 경합 재현(scratch `race_locustfile.py`: 시드 = `gevent.sleep(2.5)`, breakpoint T=500, `-t 10s`) → 시드 시작 1회·완료 1회, 그 뒤 3→6→9→12명 램프. CR-001 때는 시작 10회·완료 0회
  - 시드 정지 변형(같은 파일, sleep 20초, load T=2, `-t 5s`) → wall 25초, exit 1. `-t`가 시드 시간만큼 밀린다는 걸 확인(아래 #10)
  - selfcheck 되돌리기 5종(각각 실행 후 `cp` 복원, `shasum -c` OK): (A) #2 게이트 제거 (B) 게이트의 `reset_time()`만 제거 (C) `STATE_INIT` 조건만 제거 (D) #3 `_onset_users = None` 제거 (E) #4 `invalid json` try 제거 → 5종 모두 AssertionError/예외로 실패. 복원 후 selfcheck OK

**CR-001 처리 결과**

| # | 위치 | 처리 | 근거 |
|---|---|---|---|
| 1 | `core/hooks.py:34-41`, `:82-83`, `:86-87` | 해결 | 시드 except에서 exit 1 + 별도 그린렛 quit. 게이트 시나리오 모두 0턴이면 실패, `runner.exceptions`가 있으면 실패. 게이트 통과 시에도 이미 1이면 덮어쓰지 않음(:102). 재현 3종 exit 1 |
| 2 | `shapes/scenario.py:77-79`, `utils/sessions.py:43-74` | 해결 | 첫 `(0,100)`은 `shape_last_tick=None` 대비 변화라 `start()` → `_start` → `test_start`가 1회 실행되고, 같은 tick이 반복되면 `start()`는 다시 불리지 않는다(runners.py:356). 시드 뒤 `_start`(0명) → `spawning_complete` → RUNNING(runners.py:137-139) → 다음 tick부터 단계표. 경합 재현 시드 1회 |
| 3 | `shapes/scenario.py:139` | 해결 | selfcheck (D) 되돌리기로 검출 |
| 4 | `utils/validation.py:22-26`, `tasks/chat.py:61-65` | 해결 | selfcheck (E) 되돌리기로 검출 |
| 5 | `core/hooks.py:53-58` | 해결 | except → `logger.exception` + exit 1, 게이트는 1을 덮어쓰지 않음 |
| 6 | `README.md:33-34` | 해결 | 게이트 시나리오 종료 코드 사유 나열 + spike/breakpoint는 합격 판정 아님 |
| 7 | `mock_openai.py` | 해결 | ruff check/format clean (`re.MULTILINE` :57) |
| 8 | `mock_openai.py:34-139` | 해결 | 4개 함수 모두 한국어 명사형 요약 + Parameters/Returns |
| 9 | `mock_openai.py` | KI-013 (이월, 변경 없음) | — |

**#2 수정의 회귀 점검**

- 시드가 조용히 실패해 0명에서 영원히 멈추는가: 예외는 모두 except로 잡혀 quit된다. 성공했는데 풀이 빈 경우는 없다(`SEED_USERS ≥ 1`, `ON CONFLICT DO UPDATE ... RETURNING`은 삽입·갱신 행 모두 반환). 다만 시드가 **멈추면**(예외 없이 대기) `-t`도 같이 멈춘다 → #10
- 시드 실패 시 quit가 실행되는가: 실행된다. quit 그린렛 → `stop()`이 spawn 그린렛 kill → test_stop → quitting 게이트. 재현 로그로 확인
- web UI 재실행: `stop()`이 `shape_last_tick=None`(runners.py:406), test_stop이 `_tokens.clear()`, 다음 `start_shape`가 상태를 INIT으로 둔다(:336) → 첫 tick이 다시 변화가 되어 test_start 재시드. 정리 실패로 이전 토큰이 남아도 `STATE_INIT` 조건이 RUNNING 전까지 막고, 시드가 `_tokens[:]`로 교체한다. 모두 단일 프로세스 gevent라 모듈 상태 경합 없음
- 게이트 tick마다 `reset_time()`: 사용자 0명 구간이라 deque·streak·onset 초기화는 영향 없음. 게이트 해제 직후 elapsed≈0에서 첫 단계 보간값이 0이면 같은 `(0,100)` tick이라 `start()` 재호출 없음, 램프는 시드 완료 시점부터 정상 보간 (selfcheck가 101초가 아닌 1초 기준 `(1,100)`을 확인)
- 시드 SQL: 두 문장 모두 파라미터 바인딩(`%s - 1`, `%s::interval`, `%s::text[]`, `%s::int[]`). `users.id`/`google_sessions.user_id`는 int라 캐스트 일치. `generate_series` 값이 서로 달라 "ON CONFLICT ... cannot affect row a second time" 없음. 갱신 대상은 `google_sub = 'loadtest-i'` 충돌 행뿐이고 `ON CONFLICT (google_sub) DO UPDATE` 의미는 그대로다. 토큰↔user_id는 RETURNING 순서와 무관하게 같은 리스트에서 짝지어짐

**새 발견**

| # | 심각도 | 위치 (file:line) | 문제 | 수정 제안 | 신뢰도 | 처리 |
|---|---|---|---|---|---|---|
| 10 | Minor | `utils/sessions.py:24-30` + `shapes/scenario.py:77-84` | shape를 쓰면 `-t`는 shape만 집행한다(main.py:567-582: run_time 타이머는 `shape_greenlet.join()` 뒤). 게이트가 시드 완료 전까지 시계를 매 tick 초기화하므로 시드가 예외 없이 대기하면 `-t`가 끝없이 밀린다. `psycopg.connect`에 `connect_timeout`이 없고(libpq 기본 무한, OS TCP 타임아웃만 적용) 문장 타임아웃도 없다. DB 패킷 드롭이나 `users` 테이블 잠금(마이그레이션 중 ALTER) 중 headless/CI 실행은 Ctrl-C 전까지 안 끝난다. 시뮬레이션: 시드 20초 + `-t 5s` → 25초 | `psycopg.connect(..., connect_timeout=10, options="-c statement_timeout=60000")`. 또는 `on_test_start`에서 `with gevent.Timeout(60): seed_sessions(...)`(기존 except가 받아 exit 1) | confirmed (메커니즘, 시뮬레이션) / plausible (실제 발생 빈도 낮음) | KI-014 |

- 테스트 공백: selfcheck는 shape·validation만 다룬다. hooks.py의 #1/#5 종료 코드 경로는 DB 없는 locust 실행으로만 검증된다(이번에 재실행해 exit 1 확인). 별도 자동 검사는 요구하지 않음
### CR-003 · 2026-11-14 · backend-code-reviewer · T-010 (리뷰 대상 T-009)
- 리뷰 대상: `monitoring-docker-compose.yaml`, `monitoring/prometheus/prometheus.yml`, `monitoring/grafana/provisioning/datasources/prometheus.yml` (+ 참조용 `docker-compose.yaml`)
- 결과: PASS_WITH_NOTES
- 검증: 파일 정독과 정적 추론만 수행. Docker 데몬 중단으로 `promtool check`, 이미지 pull, 이미지 내 `sh` 존재 확인, 실제 기동·scrape는 실행하지 못함 (PM의 `docker compose config` exit 0 외에 직접 실행한 검증 없음). `$$` 이스케이프, busybox `export` 다중 대입, 플래그 형식은 코드·Dockerfile 지식 기반 판독이며 미실행.

| # | 심각도 | 위치 | 문제 | 수정 요청 | 신뢰도 | 처리 |
|---|---|---|---|---|---|---|
| 1 | Major | `monitoring-docker-compose.yaml:27,37` | `"9090:9090"`, `"3000:3000"`은 0.0.0.0에 바인딩된다. Grafana는 기본 `admin/admin`이고 Prometheus UI는 인증이 없어서, 같은 LAN(카페·사무실 Wi-Fi)의 누구나 접속해 Grafana 관리자 권한(데이터소스 추가로 내부망 SSRF)과 전체 메트릭을 얻는다. | `"127.0.0.1:9090:9090"`, `"127.0.0.1:3000:3000"` + Grafana `GF_SECURITY_ADMIN_PASSWORD`(또는 `GF_AUTH_ANONYMOUS_ENABLED=false` 유지 + 초기 비번 변경) | confirmed (설정 기준) | KI-015 |
| 2 | Minor | `monitoring-docker-compose.yaml:14-15,48-49,64-65` | `env_file: docker.env`는 파일의 모든 변수를 주입한다. prometheus는 `QDRANT__SERVICE__API_KEY`만 필요한데 POSTGRES/REDIS 비밀번호도 받고, postgres-exporter·redis-exporter도 서로 무관한 비밀을 받는다. `docker inspect`의 `Config.Env`에 전부 노출된다. 또한 `docker compose config`는 env_file을 값까지 풀어 출력하므로(PM이 이미 1회 실행) 터미널·로그·에이전트 트랜스크립트에 비밀이 남을 수 있다. | 로컬 한정이라 허용 가능(D-012). 개선하려면 서비스별 `environment: [QDRANT__SERVICE__API_KEY]`처럼 이름만 나열(호스트 셸/`--env-file` 필요)하거나 최소 변수만 담은 별도 env 파일. `config` 출력은 공유 금지, 필요하면 `config --no-interpolate`가 아닌 `--quiet` 사용. | confirmed | KI-016 |
| 3 | Minor | `monitoring-docker-compose.yaml:76` | `--kafka.version=3.9.0`은 sarama가 파싱하는 값이어야 하고(v1.9.0 번들 sarama가 3.9를 아는지 미확인), 브로커가 4.x면 KIP-896로 구 API 버전이 제거되어 sarama가 협상하는 요청 버전이 거부될 수 있다. 브로커 버전(`apache/kafka:latest`)이 고정되지 않아 `latest`가 바뀌면 깨질 수 있다. 실패 시 증상은 kafka-exporter 로그의 `Error Init Kafka Client`/lag 메트릭 부재. 컨슈머 그룹 lag(목적)이 안 나오면 모니터링 가치 상실. | 기동 직후 `curl kafka-exporter:9308/metrics | grep kafka_consumergroup_lag` 로 확인. 실패하면 `--kafka.version`을 sarama 지원 최댓값으로 조정. 근본 해결은 main 스택 `apache/kafka` 버전 고정. | plausible (미실행) | KI-017 |
| 4 | Minor | `monitoring-docker-compose.yaml:17-25` | `/tmp/qdrant_api_key`는 컨테이너 쓰기 레이어에 남고, `QDRANT__SERVICE__API_KEY`가 비어 있으면 빈 파일이 만들어져 Qdrant가 401을 반환(up=0)하며 원인 파악이 어렵다. 이스케이프 `$$`는 올바르며(compose가 `$`로 변환 → sh가 전개), `printf '%s'`로 개행 없이 쓰는 것도 맞다. | `: "${QDRANT__SERVICE__API_KEY:?missing}"`를 `&&` 앞에 추가해 빈 값이면 즉시 실패. 선택사항. | confirmed | 미처리 |
| 5 | Minor | `monitoring-docker-compose.yaml:80-88` | cadvisor `privileged: true` + 호스트 `/` ro 마운트. Docker Desktop(macOS)에서는 VM 루트를 보며 컨테이너 `name` 라벨이 비어 id만 나오는 경우가 흔해 대시보드에서 서비스 구분이 어려울 수 있다. 로컬 한정이라 보안 영향은 낮다. | 필요한 경우 `--docker_only=true` 등으로 라벨 확인. `privileged` 대신 `devices: /dev/kmsg`는 Docker Desktop에서 불필요할 수 있음. | plausible | 미처리 |
| 6 | Minor | `monitoring-docker-compose.yaml:44-58` | postgres-exporter가 앱과 같은 `POSTGRES_USER`(슈퍼유저)로 접속한다. 읽기 전용 모니터링에는 과권한. | 로컬 한정이라 허용. 필요 시 `pg_monitor` 롤 전용 계정. | confirmed | 미처리 |

확인 결과 문제 없음 (근거 포함):
- `$$` 이스케이프: compose는 `$$`→`$`로 바꾸고 컨테이너 sh가 전개하므로 올바르다 (prometheus, postgres-exporter 둘 다).
- `>-` 접기 스칼라는 줄바꿈을 공백으로 합쳐 한 줄 `export A="$POSTGRES_USER" B=... C=... && exec ...`가 된다. busybox ash는 다중 대입 `export A=.. B=..`와 큰따옴표 안의 `?`를 문제없이 처리한다. 비밀번호는 URI가 아닌 `DATA_SOURCE_PASS`에 있어 URL 인코딩 문제가 없다. 변수가 비어도 값은 따옴표로 보호된다.
- `sh` 존재: `prom/prometheus`와 `postgres-exporter`는 둘 다 `quay.io/prometheus/busybox` 기반 이미지로 알려져 있어 `/bin/sh`가 있다(Dockerfile 지식, 미실행). `/bin/prometheus`, `/bin/postgres_exporter` 경로도 공식 Dockerfile과 일치. kafka-exporter는 셸이 필요 없는 `command:` 방식이라 안전.
- Prometheus 3.x `authorization.type: Bearer` + `credentials_file` 문법 유효, 파일은 스크레이프마다 다시 읽는다. nobody 사용자가 쓰는 `/tmp`는 쓰기 가능.
- Qdrant는 `Authorization: Bearer <key>`를 `api-key` 헤더와 동등하게 인정한다.
- redis_exporter는 `REDIS_PASSWORD` 환경변수를 직접 읽으며 `REDIS_ADDR=redis://redis:6379`는 올바른 형식.
- `down`/`--remove-orphans` 안전성: 프로젝트 이름이 `rag_chatbot_monitoring`로 고정이라 `com.docker.compose.project` 라벨이 달라 메인 프로젝트 컨테이너·볼륨을 대상으로 삼지 않는다. 외부 네트워크(`external: true`)는 `down`이 삭제하지 않는다. `down -v`도 `prometheus_data`, `grafana_data`만 지운다. 주의: 메인 스택이 먼저 떠 있지 않으면 네트워크 부재로 `up`이 실패한다(문서화됨). 메인 프로젝트 이름이 `rag_chatbot`이 아니면(`-p`, `COMPOSE_PROJECT_NAME`) 네트워크 이름이 어긋난다.
- 호스트 8080 충돌 없음(cadvisor는 포트 미공개, Prometheus는 도커 네트워크 내부 `cadvisor:8080`으로 접근). 컨테이너 이름이 메인 스택과 겹치지 않음.
- 이미지 태그가 모두 고정(v3.5.0, 12.0.0, v0.17.1, v1.67.0, v1.9.0, v0.52.1).

검토하지 않은 것: 실제 기동·scrape 결과(`/targets`), 대시보드(프로비저닝된 것 없음, 데이터소스만), 백엔드 `/metrics`(후속 작업), `promtool` 설정 검증.
테스트 공백: 인프라 설정이라 자동 테스트 없음. 데몬 복구 후 권장 스모크: `docker run --rm --entrypoint promtool -v ...prometheus.yml prom/prometheus:v3.5.0 check config`, `up` 후 `http://localhost:9090/targets`에서 6개 job 모두 UP인지, `kafka_consumergroup_lag`와 `qdrant_` 메트릭 존재 확인.
- 재리뷰: 없음


### CR-005 · 2026-11-14 · backend-code-reviewer · T-013 (리뷰 대상 T-015 + T-009 CR-003 수정분)
- 리뷰 대상: `backend/app/main.py`, `core/constants.py`, `pyproject.toml`, `backend/tests/test_main.py`, `monitoring-docker-compose.yaml`, `monitoring/prometheus/prometheus.yml`, 설치된 `prometheus_fastapi_instrumentator` 8.1.0 소스
- 결과: PASS_WITH_NOTES
- 검증: 설치 소스에서 `instrument()`가 `app.add_middleware(PrometheusInstrumentatorMiddleware, ...)`임을 확인, 기본값 `should_group_status_codes=True`·`should_group_untemplated=True` 확인. 변경을 stash한 상태에서도 `tests/services/test_model_registry.py`가 `ModuleNotFoundError: clients`로 수집 실패 -> 기존 실패로 확인(단일 파일 실행 기준, stash 복원 확인). 신규 테스트·전체 스위트는 PM 결과를 신뢰하고 재실행하지 않음. Docker 데몬 중단으로 런타임 검증 없음.

| # | 심각도 | 위치 | 문제 | 수정 요청 | 신뢰도 | 처리 |
|---|---|---|---|---|---|---|
| 1 | Minor | `main.py:88` | `/metrics` 무인증 + 호스트 :8000 공개. 같은 LAN에서 경로·트래픽·지연 조회 가능. 프론트 nginx는 `/api/`만 프록시하므로 :5173으로는 미노출(CR-004 확인) | 로컬 한정이면 허용, 배포 시 프록시에서 차단 | confirmed | KI-020 |
| 2 | Minor | `main.py:84` | 멀티 워커 시 프로세스별 레지스트리라 메트릭이 워커마다 갈림. 현재 단일 프로세스라 영향 없음 | 워커 증설 전 `PROMETHEUS_MULTIPROC_DIR` 설정 | confirmed (소스 확인) | KI-021 |
| 3 | Minor | `tests/test_main.py` | `API_CALL_LOG_EXCLUDED_PATHS`에 `/metrics`가 들어갔는지, 미매칭 404가 `handler="none"`으로 묶이는지는 테스트되지 않음 | 선택 사항 | plausible | 미처리 |

확인 결과 문제 없음:
- 미들웨어 순서: Starlette는 `add_middleware`를 리스트 앞에 삽입하므로 `ApiCallLogMiddleware` 뒤에 `instrument()`를 호출하면 Instrumentator가 최외곽이다. `instrument()`는 시작 전 `add_middleware`라 유효. `expose()`는 라우트 추가이며 `include_in_schema=False`로 OpenAPI 제외.
- 라벨 카디널리티: 라우트 템플릿 기준, 미매칭은 `none`, 상태코드는 2xx/4xx/5xx 그룹(의도), `inprogress_labels=True`는 method+handler 한정이라 유계. `/metrics` 자체는 `excluded_handlers`로 계측 제외, `API_CALL_LOG_EXCLUDED_PATHS`에도 있어 DB 로그 오염 없음.
- 규칙: 서비스 계층 밖 로깅 추가 없음, 주석 한국어.
- T-009 수정: prometheus/grafana 포트가 `127.0.0.1:`로 제한됨. `: "$${QDRANT__SERVICE__API_KEY:?...}"` 가드는 compose `$$`->`$` 후 sh가 전개하므로 올바르고, 변수가 비면 `&&` 앞에서 종료해 빈 키 파일 생성을 막는다. `extra_hosts: host.docker.internal:host-gateway` 유효. `api` job 타깃(`host.docker.internal:8000`)은 uvicorn이 컨테이너에서 도달 가능한 주소(`0.0.0.0`)에 바인딩돼야 하며 `--reload --port 8000` 기본 `127.0.0.1`이면 DOWN일 수 있음(런타임 미확인, 실행 시 `--host 0.0.0.0` 확인 필요). `docker compose config`는 실행하지 않음.
- KI-015: 바인딩은 수정, Grafana 기본 비밀번호가 남아 PARTIAL(Minor)로 하향.

검토하지 않은 것: 실제 기동·scrape·`/targets`, 전체 스위트 재실행. 테스트 공백: 위 #3.
- 재리뷰: 필요 없음


### CR-006 · 2026-11-14 · backend-code-reviewer · T-017 (리뷰 대상 T-015 추가분: LOG_INFRA_ENDPOINTS)
- 리뷰 대상: `core/config.py`, `core/constants.py`, `core/logging_config.py`, `middlewares/api_call_log_middleware.py`, 해당 테스트 2개 파일, 설치된 uvicorn 0.49.0 소스(`AccessFormatter.formatMessage`, h11 access 로깅)
- 결과: PASS_WITH_NOTES
- 검증: `uv run pytest -k "logging_config or api_call_log"` (backend/app에서) 19 passed. 전체 스위트는 PM 결과(100 passed / 2 failed, 기존 model_registry 실패)를 신뢰하고 재실행하지 않음.

| # | 심각도 | 위치 | 문제 | 수정 요청 | 신뢰도 | 처리 |
|---|---|---|---|---|---|---|
| 1 | Minor | `logging_config.py:35` | 위치 인자 `args[2]` 의존. uvicorn 0.49.0은 `(client_addr, method, full_path, http_version, status)` 튜플로 확인(`AccessFormatter`가 동일하게 언패킹)되어 현재 정상. uvicorn 업그레이드로 args 형태가 바뀌면 필터가 조용히 통과(fail-open)로 바뀌어 헬스체크 로그가 다시 보일 뿐 해롭지 않음 | 조치 불필요. uvicorn 메이저 업 시 테스트의 레코드 형태 확인 | confirmed (소스) | 미처리 |
| 2 | Minor | `logging_config.py:34-35`, `constants.py:27` | 동작 변경: `/`가 uvicorn access 로그에서도 사라짐(LOG_INFRA_ENDPOINTS=False 기본). 사용자 요청은 /health·/metrics이나 `/`는 이미 API 호출 로그 제외 대상이라 일관적. 의도면 문제 없음 | 의도 확인만 | confirmed | 미처리 |
| 3 | Minor | 테스트 | `/healthz`, `/metrics-foo`, `/metrics/x`가 통과(비제외)하는 음성 케이스와 `/`의 제외·미들웨어 플래그 False 시 `/metrics` 제외 테스트가 없음(기존 `/health` 제외 테스트는 있음). 구현은 정확 일치(`in frozenset`, 쿼리스트링만 제거)라 실제로는 올바름 | 선택: parametrize에 `/healthz`, `/metrics-foo` 추가 | confirmed (코드 추론) | 미처리 |

확인 결과 문제 없음:
- args 파싱: 위 #1. `len(record.args or ())` 가드로 빈 args는 안전. 쿼리스트링(`/metrics?x=1`)은 `split("?",1)[0]`로 제거.
- 중복 등록 방지: `any(isinstance(...))` 가드로 API·워커가 여러 번 호출해도 1개(테스트로 2회 호출 검증). 워커는 uvicorn을 쓰지 않아 부착돼도 무해. uvicorn은 앱 import 전에 dictConfig를 수행하고 dictConfig는 기존 로거 필터를 지우지 않으므로 순서 문제 없음. `root.handlers` 교체는 `uvicorn.access`(자체 핸들러, propagate False)에 영향 없음.
- /api 트래픽 미은닉: 집합 정확 일치라 `/healthz`, `/metrics-foo`, `/api/...`는 통과. 미들웨어는 `request.url.path` 정확 일치, 플래그 True면 전부 기록, False일 때 `/health`·`/`는 종전과 동일하게 제외(+`/metrics` 추가).
- 규칙: 서비스/워커 계층 밖 로깅 "호출" 추가가 아니라 로깅 인프라(`core/logging_config.py`) 내 필터이므로 위반 아님. 주석·docstring 한국어. 레코드마다 `config` 속성 읽기는 O(1).

검토하지 않은 것: 실제 uvicorn 기동으로 access 로그 소거 확인(소스·단위 테스트 기준으로만 판단). 테스트 공백: 위 #3.
- 재리뷰: 필요 없음
### CR-007 · 2026-11-14 · backend-code-reviewer · T-019 (리뷰 대상 T-018)
- 리뷰 대상: `monitoring-docker-compose.yaml`(loki, alloy, loki_data, grafana depends_on), `monitoring/loki/loki-config.yaml`, `monitoring/alloy/config.alloy`, `monitoring/grafana/provisioning/datasources/loki.yml`, `monitoring/prometheus/prometheus.yml`
- 결과: PASS_WITH_NOTES (차단 이슈 없음)
- 검증: 파일 정독과 Loki 공식 문서(context7 `/grafana/loki`) 대조. PM의 `docker compose config` exit 0은 재실행하지 않았다. Docker 데몬 중단으로 `loki -verify-config`, `alloy fmt`, 실제 기동·수집·Grafana 쿼리는 실행하지 못함. 렌더된 compose 출력은 비밀 포함이라 보지 않음.

| # | 심각도 | 위치 | 문제 | 수정 요청 | 신뢰도 | 처리 |
|---|---|---|---|---|---|---|
| 1 | Minor | `monitoring-docker-compose.yaml:alloy` (`--storage.path=/var/lib/alloy/data`) | Alloy 데이터 디렉터리에 볼륨이 없어 `up --force-recreate`/이미지 교체 시 읽기 위치(positions)가 사라진다. 재시작(restart)만으로는 컨테이너 파일시스템이 유지되어 무해. 재생성 직후 기존 컨테이너 로그를 다시 push할 수 있으나 Loki가 동일 (스트림, 시각, 라인)은 중복 제거한다. | `alloy_data:/var/lib/alloy/data` named volume 추가(선택). | plausible (미실행) | KI-022 |
| 2 | Minor | `loki-config.yaml` | `analytics.reporting_enabled` 기본값이 true라 Loki가 사용 통계를 grafana.com으로 전송한다. 로컬 개발 스택에서 불필요한 외부 호출. | `analytics: { reporting_enabled: false }` | confirmed (Loki 기본값) | KI-022 |
| 3 | Minor | `config.alloy` (loki, alloy 컨테이너 포함 전체 수집) | 피드백 루프는 Loki 장애 시에만 가능: Alloy의 push 실패 에러 로그가 다시 Loki로 보내져 또 실패한다. 배치당 에러 1줄이고 백오프가 있어 증폭되지 않고 Loki 복구 시 해소된다. 정상 시에는 Loki 로그레벨이 warn이라 루프 없음. | 조치 불필요. 노이즈가 싫으면 `discovery.relabel`에 `container` 가 `loki\|alloy`인 `keep/drop` 규칙. | confirmed (정적 추론) | 미처리 |
| 4 | Minor | `datasources/loki.yml` | `uid` 미지정이라 Grafana가 임의 uid를 생성하고, 이후 대시보드 JSON을 프로비저닝할 때 참조하기 어렵다. | `uid: loki` 고정(대시보드 추가 시점에). | plausible | 미처리 |

확인 결과 문제 없음 (근거 포함):
- Loki 3.6 단일 바이너리: `schema v13` + `tsdb` + `filesystem` 조합 유효(구조화 메타데이터 요건 충족). `common.path_prefix: /loki` 하나로 WAL(`/loki/wal`), compactor, TSDB `active_index_directory`/`cache_location` 기본값이 모두 `/loki` 하위로 잡힌다(공식 `applyPathPrefixDefaults` 및 TSDB 디렉터리 문서). 이미지는 `/loki`를 uid 10001 소유로 만들고, 빈 named volume은 이미지 디렉터리의 소유권을 복사받으므로 쓰기 가능(이미지 Dockerfile 직접 확인은 못함). 보존: `retention_enabled: true` + `delete_request_store: filesystem`(필수 항목) + `limits_config.retention_period: 168h`로 완비, Prometheus 7d와 일치. 데몬 복구 후 `loki -verify-config`로 최종 확인 권장.
- Alloy 문법: `discovery.docker` → `discovery.relabel`(`targets = []`, `rules`) → `loki.source.docker`(`targets` + `relabel_rules`) → `loki.write` 구성은 유효한 패턴. 라벨은 `container`, `compose_project`, `compose_service`로 저카디널리티(컨테이너 수 ≈ 15 이하). 라벨 정규식 `/(.*)`는 Docker 컨테이너명의 선행 `/`를 제거한다.
- Prometheus 스크레이프: Alloy 기본 listen은 `127.0.0.1:12345`지만 compose의 `--server.http.listen-addr=0.0.0.0:12345`로 열려 `alloy:12345` 잡이 유효. 호스트 포트는 미공개(D-012 준수). Loki `loki:3100/metrics`도 기본 경로로 유효.
- 소켓/권한: `docker.sock:ro`는 소켓 파일의 mount 쓰기만 막을 뿐 Docker API 호출(컨테이너 생성·삭제·exec)은 제한하지 않는다. compose 주석에 "Docker API 자체는 쓰기도 가능, 로컬 개발 전용"과 root 실행 사유가 명시되어 있어 문서화 요건 충족(D-012 수용 범위). Alloy 컨테이너 침해 = 호스트 Docker 장악이라는 점은 유지.
- 비밀: loki/alloy에 `env_file` 없음(KI-016 범위 확대 없음). 이미지 태그 고정(`3.6.7`, `v1.12.2`). 호스트 포트 추가 없음. Grafana → Loki는 `http://loki:3100` 내부 접속. `depends_on`은 기동 순서만 보장하며 Alloy/Grafana는 Loki 준비 전 재시도하므로 무해.
- 범위 한계: 호스트에서 실행되는 API 로그는 수집되지 않음(주석에 명시, 알려진 제약).

검토하지 않은 것: 이미지 태그 실존, 실제 기동과 로그 유입, LogQL 조회, 디스크 사용량(7일 보관 시 로그량 추정).
- 재리뷰: 필요 없음. 데몬 복구 후 권장 스모크: `docker run --rm -v ./monitoring/loki/loki-config.yaml:/c.yaml grafana/loki:3.6.7 -config.file=/c.yaml -verify-config`, `alloy fmt`, Prometheus Targets에서 loki·alloy UP, Grafana Explore에서 `{compose_service="loki"}` 조회.
