# 사용자 요구사항 대조

| 요구 | 반영 위치 | 확인 범위 |
| --- | --- | --- |
| 5종 문서 가이드와 예시 | rules/ | 기존 합의 문서 보존 |
| 조사부터 단계와 유형별 MD | flow.py, policies/artifacts.json | 분류·추가 등록·담당자 검사 |
| 폴더별 INDEX | indexes.py | 자동 안내와 작성 목차 보존 |
| 읽는 문서에 관리 번호 제외 | md_contract.py, 출력 어댑터 | 내부 ID·출처 경로 비출력 테스트 |
| 회사/제품/환경 분리 | config/catalog.json, config/, examples/demo/ | demo 명시 연결, 경로 범위 검사 |
| 표·폰트·제목·공용 양식 | 회사 theme.json | 역할별 스타일·표지·저작권·목차·머릿글·바닥글·마지막 페이지 |
| Word/Excel/HTML 출력 | creator.py, output_adapters.py | 4형식 생성, PDF/HTML 시각 검수 |
| Python 3.12 | .python-version, doctor.py | 실제 3.12 실행 |
| 병렬 캡처·페이지 분배 | collect.py | 실제 다중 프로세스 테스트 |
| 테마·언어·해상도별 캡처 | profile와 페이지 설정 | 실제 dark/en-US/640×480 및 경로 검증 |
| 로딩·API 타임아웃 | wait_for_responses/ready_selector | 실제 응답 및 Timeout 검증 |
| 계정 로그인 | 환경변수 또는 storageState | 로컬 로그인, 비밀 미출력 |
| PostgreSQL 조회만 | collector/postgres.py | 로컬 PostgreSQL 실제 조회·권한 거부·시간 제한·중단/복구 검증; 운영 DB 별도 검증 필요 |
| 시니어 문서팀·여러 에이전트 | roles/workflows/ai_runner.py | 역할·병렬 작업사본·실패·게이트 |
| 새로운 조사 대상 추가 | flow add | 분류/중복/INDEX 갱신 테스트 |
| Git 연결과 최초 커밋 | origin + check_staged.py | 비밀·생성 결과 제외 후 커밋 |

실제 회사 서식과 제품 접속정보가 없는 항목은 가상 데이터를 실제 완료 증거로 바꾸지 않는다. 지원하지 않는 고급 레이아웃과 실환경 미검증은 STATUS.md에 기록한다.
