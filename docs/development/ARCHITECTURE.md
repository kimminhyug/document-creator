# 구현 구조

## 데이터 흐름

설정 → 자료 수집 → 분류 MD/관리 JSON → 역할별 작업 → 단계 검사 → 회사 서식 출력 → 형식별 검수 → 전달 순서로 처리한다.

| 구성 | 책임 |
| --- | --- |
| config_paths.py | 실제 설정과 명시 등록한 데모 위치 해석 |
| collector/config.py | 제품·환경·캡처·조회 정책 검사 |
| collect.py / browser_worker.cjs | Python 3.12 병렬 조정과 Playwright 브라우저 수집 |
| collector/postgres.py | 구조화된 SELECT와 제한된 조회 실행 |
| prepare_ai.py | 검증된 수집 파일로 로컬 AI 입력 묶음 생성 |
| flow.py | 파일 등록, 담당자, 단계 통과·재작업·해시 |
| md_contract.py | 읽는 MD와 관리 JSON 분리, 분류·필수 항목 검사 |
| indexes.py | 폴더별 안내 링크 갱신 |
| ai_runner.py | 공급자 독립 명령 실행, 작업사본 분리, 제한·실패 기록 |
| md_build.py | 여러 MD를 임시 출력 모델로 조합 |
| company_build.py | 회사 승인 테마·제품 문구 선택 |
| creator.py / output_adapters.py | Word/PDF/HTML/Excel 출력 |

## 변경과 검수

본문이나 메타데이터·근거·검수 파일이 바뀌면 이전 단계 통과를 새 내용에 적용하지 않는다. rework로 영향 단계부터 다시 확인한다. 생성 결과는 새 실행 디렉토리에 보존하며 실패한 출력은 완료 폴더로 공개하지 않는다.

PDF는 독립 ReportLab 레이아웃이며 Word 변환본이 아니다. Word/Excel의 앱 화면 확인은 별도 증거가 필요하다. 모델 응답이나 테스트 통과만으로 업무 사실 또는 전체 제품을 승인하지 않는다.
