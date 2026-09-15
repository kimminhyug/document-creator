# 디렉토리와 문서 인터페이스 정책

## 분류 원칙

제품이 달라도 같은 분류·파일 계약을 적용한다. 루트 INDEX.md부터 시작하여 폴더별 INDEX.md를 따라 탐색한다. 한 폴더에 조사·본문·정책·테스트를 섞지 않는다.

~~~text
config/
  catalog.json                 회사·제품 위치 등록
  companies/{company}/         실제 회사 공통 서식
  products/{product}/          실제 제품·환경·문서별 설정
examples/demo/
  companies/demo/             가상 회사 테마
  products/demo/              가상 페이지·DB·workflow 설정
  content/                    출력 어댑터용 가상 데이터
rules/                        5종 작성 가이드
policies/                     MD 분류와 필수 항목
workflows/                    단계 순서와 게이트
roles/                        역할과 담당자 기본값
profiles/capture/             캡처 프로필
workspaces/{company}/{product}/{run}/
  INDEX.md
  scope/
  sources/                    수집 파일과 내부 연결 정보
  research/inventory/
  research/architecture/
  research/behavior/pages/
  research/data/apis/
  research/data/metrics/
  research/data/tables/
  research/reconcile/
  outlines/
  documents/{type}/INDEX.md
  documents/{type}/sections/
  reviews/facts/
  reviews/independent/
  reviews/style/
  delivery/
  tasks/                      역할별 작업 요청
  agent-runs/                 실행 성공·실패 기록
  .metadata/                  MD와 대응되는 관리 JSON
~~~

폴더별 INDEX에는 문서 제목과 상대 링크를 기록한다. 자동 INDEX는 init·task·단계 변경 때 갱신하며, 별도 자료 추가 후에는 indexes.py에 대상 폴더를 지정한다. 사람이 작성한 문서 목차 INDEX는 자동 덮어쓰기하지 않는다.

회사/제품 ID는 등록용 고유 이름이다. demo는 catalog에서 examples/demo로 명시 연결되어 있다. 실제 회사는 config/companies에, 실제 제품은 config/products에 추가한다. 다른 제품의 설정을 묵시적으로 대체하지 않는다.

## 사람이 읽는 문서

MD 본문에 내부 출처 번호·해시·JSON 주석·관리용 절 ID를 쓰지 않는다. 근거가 필요하면 자료명·화면명·링크처럼 이해할 수 있는 이름을 쓴다. 업무에 필요한 실제 API 필드명·DB 컬럼명은 해당 독자용 문서에 유지한다.

예: research/behavior/pages/summary.md에는 화면 설명만 쓰고, 관리 정보는 .metadata/research/behavior/pages/summary.md.json에 둔다. id/kind/company/product/status/sources/author는 그 JSON의 필수 필드다. 과거 실행의 첫 줄 주석은 읽기 호환만 유지하며 새 MD에는 만들지 않는다.

본문 상태는 자연어로 설명하고 관리 상태는 pending / confirmed / not_applicable로 기록한다. 리뷰는 verdict=pass가 필요하다. 공개 참고자료는 문서 목차의 관리 JSON public_references에 제목과 공개 URL을 지정한 경우만 출력한다.

Markdown은 2~4단계 제목, 문단, 표, 코드, NOTE/WARNING/EXAMPLE, 등록된 PNG/JPEG 이미지를 지원한다. 모든 GFM 서식과 수식 렌더러를 지원하는 것은 아니다. 표는 1~6열로 나누며 의미를 유지한다.

## 설정 우선순위

1. 공통 분류·워크플로·문서 계약.
2. 회사가 승인한 서식·캡처 프로필·허용 문서 유형.
3. 제품의 문서별 담당자·페이지·데이터·환경 설정.
4. 실행별 원본·관찰·검토 기록.

내용이 회사 테마를 덮어쓰지 않는다. 역할별 글꼴·크기·굵기, 표 헤더색·테두리·여백, 표지·저작권·목차·머릿글·바닥글·끝 페이지는 회사 theme.json이 기준이다. 공통 theme는 예제 기본값이며 회사 공식 양식으로 자동 승인되지 않는다.

## 단계·출력 계약

12단계는 workflows/senior-document-team.json을 따른다. 문서별 document_teams 또는 파일별 agent로 담당을 나눈다. 같은 작성자가 독립 리뷰를 맡을 수 없다. 에이전트 ID는 감사 식별자이며 인증 시스템은 아니다.

통과한 MD·관리 JSON·근거 또는 검수한 출력이 변경되면 후속 단계 진행을 막는다. lead가 사유와 복귀 단계를 지정해 rework한 뒤 다시 검증한다. 실제 출력 없는 전달, 검수 단계의 해당 없음 처리는 허용하지 않는다.

서식 검수·전달 관리 JSON의 outputs에는 작업폴더 내부 path, format, sha256, review_status=passed, reviewer, review_notes를 기록한다. 요청 형식은 제품 workflow plan의 formats로 지정한다. 기본 pdf이며 docx/xlsx/html도 가능하다. 렌더 결과는 delivery/files에 복사해 검수하고 해당 파일의 해시를 기록한다. 검수 기록을 작성하는 주체가 실제 출력의 해당 형식을 확인해야 한다.

임의 실행기의 접근권한은 OS에서 관리한다. 생성기 내부 경로 검사와 작업사본 분리는 악성 로컬 프로그램에 대한 보안 샌드박스가 아니다.

## 조사 대상 추가

조사 중 새 API·화면·테이블을 발견하면 lead가 새 파일의 종류·단계·상대 경로·제목을 담은 JSON을 작성하고 아래 명령으로 등록한다. 지난 단계에 추가하려면 먼저 rework한다. 등록 후 폴더 INDEX가 갱신된다.

~~~text
python flow.py add --run 작업폴더 --record 새대상.json --actor document-lead
~~~
