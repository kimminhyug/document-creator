# 캡처 설정 가이드

제품 environments/{environment}.json에서 base_url, allowed_origins, capture_profile, capture 파일을 연결한다. 승인된 테스트 환경과 조회 범위만 사용한다.

## 공통 프로필

profiles/capture/{name}.json 예시:

~~~json
{
  "workers": 2,
  "color_scheme": "dark",
  "locale": "ko-KR",
  "timezone": "Asia/Seoul",
  "viewport": {"width": 1440, "height": 900},
  "timeout_ms": 15000,
  "navigation_timeout_ms": 30000,
  "api_timeout_ms": 45000,
  "overlap_px": 120,
  "max_segments": 12
}
~~~

테마는 브라우저의 light/dark 색상 선호 설정이다. 제품 내부의 별도 테마 저장 설정이 있다면 인증 상태에 반영하거나 제품이 해당 선호 설정을 지원하는지 확인한다. 언어도 브라우저 locale 기준이며 애플리케이션 자체 언어 설정과 같다고 가정하지 않는다.

- timeout_ms: 요소 준비와 캡처의 기본 제한.
- navigation_timeout_ms: 페이지 이동 제한.
- api_timeout_ms: 지정 API 응답과 응답 본문 수신 제한.
- workers: 별도 Playwright 프로세스 수(1~8).
- viewport: 브라우저 화면 해상도. 긴 화면은 overlap_px만큼 겹쳐 분할한다.

## 페이지 규칙

~~~json
{
  "pages": [{
    "id": "summary",
    "path": "/summary",
    "mode": "segments",
    "ready_selector": "[data-loaded=true]",
    "masks": [".private"],
    "output_subdir": "manual/dashboard",
    "filename": "performance-summary",
    "wait_for_responses": [{"path": "/api/summary", "method": "GET", "status": 200}]
  }]
}
~~~

API 대기는 페이지 이동 전에 등록한다. URL과 메서드·상태가 일치해야 하며 쿼리 문자열도 포함된다. 응답만 받았다고 화면이 준비됐다고 가정하지 않고 ready_selector도 확인한다. masks에 지정한 요소가 없으면 민감정보 노출을 피하기 위해 캡처를 실패 처리한다.

mode는 viewport / segments / element이며 element는 selector가 추가로 필요하다. 임의 JS나 임의 클릭 시나리오는 설정에서 실행하지 않는다.

위 예시 출력은 screenshots/manual/dashboard/dark/ko-KR/1440x900/performance-summary-001.png이다. 기본 파일명은 페이지 ID이며 테마·언어·해상도는 항상 경로에 포함된다. 경로와 파일명은 안전한 영문 kebab-case를 사용한다. 실행 루트에는 제품·환경·실행 시각이 포함된다.

## 로그인

환경 설정에는 값 대신 환경변수 이름과 selector를 넣는다. 아래는 demo/local에 대응하는 예시이며 실제 사용 시 제품과 환경 이름으로 변경한다.

~~~json
{
  "login": {
    "path": "/login",
    "username_env": "DOC__DEMO__LOCAL_LOGIN_USERNAME",
    "password_env": "DOC__DEMO__LOCAL_LOGIN_PASSWORD",
    "username_selector": "#username",
    "password_selector": "#password",
    "submit_selector": "button[type=submit]",
    "success_selector": "[data-login=success]"
  }
}
~~~

자격 증명은 프로세스 환경에서 읽어 메모리로 전달한다. 설정 파일·인자·산출물 로그에 저장하지 않는다. DB 비밀번호는 별도 DOC__DEMO__LOCAL_PASSWORD이므로 웹 로그인과 섞이지 않는다.

SSO/MFA 등 복잡한 로그인은 운영자가 확보한 Playwright storageState 파일을 .local/에 두고 환경의 auth_state_env로 경로 변수를 참조한다. login과 auth_state_env는 동시에 설정하지 않는다. 세션 파일은 비밀번호와 같은 수준으로 관리하며 Git에 올리지 않는다.

## 실행과 한계

~~~text
python examples/demo/tools/demo_capture_server.py
python collect.py --product demo --environment local
~~~

DB 조회는 --with-db를 명시할 때만 수행한다. 실제 PostgreSQL 서버 검증은 운영자가 읽기 전용 권한을 준비한 후 진행한다. 안전한 구조화 조회·READ ONLY·권한 검사·시간/행 제한을 함께 사용한다. SELECT에서 호출되는 사용자 함수와 승인 View 자체의 부작용은 DB 정책으로 제한해야 한다.

검증은 로컬 테스트 제품에서 수행했다. 실제 제품의 locator·인증·API 응답 계약은 제품별로 확인한다.
