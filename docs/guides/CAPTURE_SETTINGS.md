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

로그인 성공 선택자가 나타난 뒤 같은 탭에서 about:blank로 이동하고 대상 페이지를 다시 연다. 쿠키·localStorage뿐 아니라 탭에 묶인 sessionStorage 인증도 유지하기 위해 새 탭으로 바꾸지 않는다. 이 과정은 로그인 주소와 캡처 주소가 같거나 hash만 다른 단일 페이지 앱에서도 대상의 실제 HTTP 응답을 검증하기 위한 것이다. 필수 API 응답 대기는 빈 문서로 이동한 뒤 대상 탐색 전에 등록한다. 따라서 로그인 화면의 이전 응답을 대상 화면의 준비 증거로 사용하지 않는다.

페이지를 다시 열면 사라지는 JavaScript 메모리 전용 로그인 상태는 지원하지 않는다. 대상 URL을 새로 열어도 인증을 복구할 수 있는 쿠키 또는 브라우저 저장소 방식이 필요하다. 로그인 선택자는 제품 화면에 실제로 존재하는 값이어야 하며 성공 선택자는 인증이 끝났음을 나타내는 요소로 정한다.

SSO/MFA 등 복잡한 로그인은 운영자가 확보한 Playwright storageState 파일을 .local/에 두고 환경의 auth_state_env로 경로 변수를 참조한다. login과 auth_state_env는 동시에 설정하지 않는다. 세션 파일은 비밀번호와 같은 수준으로 관리하며 Git에 올리지 않는다.

storageState는 쿠키·localStorage 등을 복원하지만 sessionStorage 인증을 자동으로 복원하지 않는다. sessionStorage가 필요한 제품은 해당 제품의 로그인 설정을 사용한다.

## 실패 단계 확인

manifest.json의 captures 항목에서 실패 시 error와 stage를 확인한다. error는 Timeout 또는 CaptureFailed이며 stage는 아래 고정값 중 하나다. 원시 예외 메시지·URL·선택자·계정·비밀번호는 진단 필드에 기록하지 않는다.

| stage | 실패한 작업 |
| --- | --- |
| context | 브라우저 컨텍스트·탭·네트워크 정책 준비 |
| login_navigation | 로그인 주소 탐색과 HTTP 상태 확인 |
| login_username | 계정 입력 요소 대기·입력 |
| login_password | 비밀번호 입력 요소 대기·입력 |
| login_submit | 로그인 제출 요소 대기·선택 |
| login_success | 로그인 성공 요소 대기 |
| navigation_reset | 같은 탭의 빈 문서로 이동 |
| navigation | 대상 주소 탐색과 HTTP 상태 확인 |
| api_wait | 필수 API 응답과 본문 수신 대기 |
| ready | 대상 화면 준비 요소 대기 |
| fonts | 문서 글꼴 준비 대기 |
| masks | 필수 마스크 요소 확인 |
| segment_scroll | 긴 화면 분할 위치 이동·종료 확인 |
| capture | 캡처 대상 크기·경로 확인 및 이미지 저장 |

예를 들어 잘못된 로그인 제출 선택자는 Timeout과 login_submit으로, 준비 요소가 없는 화면은 Timeout과 ready로 구분한다. 프로세스가 종료되거나 전체 실행 한도를 넘는 등 worker 바깥에서 발생한 오류는 stage가 없을 수 있다. stage는 실패 시점의 작업을 알려주며 근본 원인을 확정하는 진단은 아니다.

## 실행과 한계

병렬 작업 수는 대상 서버의 응답 시간과 함께 정한다. 여러 검증 브라우저를 동시에 실행하면 로그인 성공 대기나 제품 자체 API 제한 시간에 걸릴 수 있다. 첫 실패 기록을 보존하고, 같은 설정의 단독 재실행 결과를 별도 실행 폴더에 남겨 비교한다. 재실행 성공이 첫 실패 기록을 지우거나 운영 부하 검증을 대신하지 않는다.

매뉴얼에 넣을 그림은 하나의 화면 패널을 담는 element 모드를 우선 검토한다. 긴 화면을 segments로 나누면 겹침 구간에서도 이미지 경계에 걸린 글자·입력칸이 잘릴 수 있으므로 모든 분할을 열어 확인한다. 픽셀상 누락이 없다는 검사만으로 사람이 읽기 좋은 캡처라고 승인하지 않는다.

~~~text
python examples/demo/tools/demo_capture_server.py
python collect.py --product demo --environment local
~~~

DB 조회는 --with-db를 명시할 때만 수행한다. 실제 PostgreSQL 서버 검증은 운영자가 읽기 전용 권한을 준비한 후 진행한다. 안전한 구조화 조회·READ ONLY·권한 검사·시간/행 제한을 함께 사용한다. SELECT에서 호출되는 사용자 함수와 승인 View 자체의 부작용은 DB 정책으로 제한해야 한다.

검증은 로컬 테스트 제품에서 수행했다. 실제 제품의 locator·인증·API 응답 계약은 제품별로 확인한다.
