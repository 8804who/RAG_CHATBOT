"""
RAG 챗봇 Locust 부하 테스트 진입점 (시나리오 설계: SCENARIOS.md, 실행 방법: README.md)

Locust는 이 모듈의 이름 공간에서 User/LoadTestShape 클래스를 찾는다. 구성:
  core/    설정·env 검증(config), 수명주기 훅(hooks: 시드·세션 삭제·합격 게이트)
  users/   ChatUser, BrowseUser
  tasks/   사용자별 task 함수
  shapes/  LOADTEST_SCENARIO 단계표 부하 모양
  utils/   시드 세션 풀, HTTP 헬퍼, 응답 검증
단일 프로세스 Locust 전용이다 (시드 세션 풀과 breakpoint 정지 규칙이 로컬 메모리·통계를 쓴다).
"""

import core.hooks  # noqa: F401  (import 시 이벤트 리스너 등록)
from shapes.scenario import ScenarioShape
from users.browse import BrowseUser
from users.chat import ChatUser

__all__ = ["BrowseUser", "ChatUser", "ScenarioShape"]
