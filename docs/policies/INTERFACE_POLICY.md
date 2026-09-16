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

코드 블록은 백틱 또는 물결표를 3개 이상 사용한다. 닫는 표시는 같은 문자이며 여는 표시 이상의 길이여야 한다. 코드 안의 제목·링크 예시는 원문 그대로 보존한다.

MD의 상대 문서 링크는 분류된 원본 탐색에 사용한다. 개별 출력은 서로 다른 폴더로 전달될 수 있으므로 문서 간 참조는 `문서명 — 절명`으로 변환한다. 배포 경로를 추정해 깨진 링크를 만들지 않는다. 본문의 웹 링크는 표시명과 주소를 함께 적고 HTML·PDF·Word에서 주소를 클릭할 수 있게 출력한다. Excel은 한 셀에 주소가 하나일 때 셀 링크를 제공하며 여러 주소이면 텍스트로 보존한다. 계정 정보가 들어간 웹 링크는 거부한다. 출처 관리 번호와 작업폴더 경로는 이 참조에 포함하지 않는다.

클릭할 웹 주소는 MD에서 `[표시명](주소)`로 명시한다. 문장에 나온 프로토콜 이름이나 Host 자리표시자를 주소로 추측하지 않는다. 예를 들어 `http://와 Host를 조합한다`는 평문이다. 변환 모델의 `web_links`는 이렇게 명시한 목적지만 담는 관리용 목록이며 독자 본문에는 출력하지 않는다. 붙어 있는 한국어 조사도 주소에 포함하지 않는다.

문서 절 파일의 `## 내용`은 본문 범위를 구분하는 필수 입력 구조이며 최종 출력에는 표시하지 않는다. 그 안의 하위 제목은 출력에서 한 단계 올려 자연스러운 제목 계층을 유지한다. 코드 블록 안의 제목 모양 문자열은 바꾸지 않는다. `관련 참조`는 실제 안내할 문서·절이 있을 때만 작성한다. 모든 절에 같은 목차 안내를 자동으로 붙이지 않는다.

## 설정 우선순위

1. 공통 분류·워크플로·문서 계약.
2. 회사가 승인한 서식·캡처 프로필·허용 문서 유형.
3. 제품의 문서별 담당자·페이지·데이터·환경 설정.
4. 실행별 원본·관찰·검토 기록.

내용이 회사 테마를 덮어쓰지 않는다. 역할별 글꼴·크기·굵기, 표 헤더색·테두리·여백, 표지·저작권·목차·머릿글·바닥글·끝 페이지는 회사 theme.json이 기준이다. 공통 theme는 예제 기본값이며 회사 공식 양식으로 자동 승인되지 않는다.

PDF는 설정된 주 글꼴이 지원하는 문자를 확인하고, 없는 문자만 기존 ReportLab 번들의 Vera 글꼴로 보완한다. 두 글꼴 모두 지원하지 않으면 문자 코드와 위치를 알리는 오류로 생성을 중단한다. 기호를 임의 치환하거나 빈칸으로 누락하지 않는다. 새 글꼴 설치나 폰트 파일의 저장소 복사는 하지 않는다. ReportLab 배포본의 `fonts/bitstream-vera-license.txt`가 해당 보완 글꼴의 라이선스 기준이다. 회사가 대체 글꼴 사용을 허용하는지는 회사 서식 검수에서 확인한다.

PDF·DOCX 테마의 `layout.keep_title_words`는 표지 제목의 단어 단위 줄바꿈, `table.column_width_mode`는 `equal`(동일 폭) 또는 `content`(내용 길이 기반 열 너비)를 정한다. 긴 표는 페이지를 나눠 반복 헤더를 붙이며 짧은 절의 묶음 높이는 `layout.keep_short_sections_max_height_mm`로 정한다. DOCX는 글자 너비와 높이를 추정하므로 글꼴·Office 프로그램에 따라 결과가 달라질 수 있다. 이 설정도 모든 실제 출력 페이지 검수를 대신하지 않는다.

DOCX는 회사가 지정한 글꼴을 기본 템플릿의 테마 글꼴보다 우선하며, 기본 Title 스타일의 장식선을 제거한다. `table.keep_rows_together`는 기본 `true`로 짧은 표 행의 페이지 분할을 막는다. 한 페이지보다 높은 행은 다음 페이지로 계속 이어질 수 있다. `false`이면 프로그램의 기본 행 분할을 허용한다. DOCX 목차는 절 목록이며 자동 페이지 번호 목차는 아직 지원하지 않는다.

제품 `document-project.json`의 `language`는 DOCX의 문서·스타일 언어 태그다. 기본값은 `ko-KR`이며 `en-US`, `zh-Hant`처럼 언어 태그를 지정한다. 한국어 단어 줄바꿈이 기본 영어 설정에 좌우되지 않게 명시한다. 이 옵션은 원문이나 공통 안내 문구를 자동 번역하지 않는다. 다른 언어 문서는 실제 렌더러에서 따로 확인한다.

한국어·일본어·중국어 문서의 라틴 문자 언어는 별도 `latin_language`(기본 `en-US`)를 사용한다. DOCX 표·일반 문장은 공백 위치에 표시되는 줄바꿈을 배치하여 어절·숫자 단위를 보존한다. 원문 Markdown은 바꾸지 않으며 숨은 결합 문자는 삽입하지 않는다. 열보다 긴 단일 문자열은 Office의 기본 줄바꿈을 사용하므로 아주 긴 주소·식별자는 별도 시각 확인이 필요하다.

## 단계·출력 계약

조사의 공통 진입점은 `document.py research`다. `plan`은 설정을 읽어 조사 대상·역할·산출물을 확인하고, `run`은 새 작업을 생성하며, `status`와 `resume`은 저장된 제품·환경에 연결된 작업을 조회·재개한다. 실제 AI 실행과 근거 수집은 명시적 옵션으로 구분한다. 실행 성공과 검토 승인을 구분하며 조사 명령이 `flow.advance`를 자동 호출하지 않는다. 상세 예시는 [조사 실행 명령](../guides/RESEARCH_COMMANDS.md)을 따른다.

12단계는 workflows/senior-document-team.json을 따른다. 문서별 document_teams 또는 파일별 agent로 담당을 나눈다. 같은 작성자가 독립 리뷰를 맡을 수 없다. 에이전트 ID는 감사 식별자이며 인증 시스템은 아니다.

통과한 MD·관리 JSON·근거 또는 검수한 출력이 변경되면 후속 단계 진행을 막는다. lead가 사유와 복귀 단계를 지정해 rework한 뒤 다시 검증한다. 실제 출력 없는 전달, 검수 단계의 해당 없음 처리는 허용하지 않는다.

서식 검수·전달 관리 JSON의 outputs에는 작업폴더 내부 path, format, sha256, review_status=passed, reviewer, review_notes를 기록한다. 요청 형식은 제품 workflow plan의 formats로 지정한다. 기본 pdf이며 docx/xlsx/html도 가능하다. 렌더 결과는 delivery/files에 복사해 검수하고 해당 파일의 해시를 기록한다. 검수 기록을 작성하는 주체가 실제 출력의 해당 형식을 확인해야 한다.

임의 실행기의 접근권한은 OS에서 관리한다. 생성기 내부 경로 검사와 작업사본 분리는 악성 로컬 프로그램에 대한 보안 샌드박스가 아니다.

## 조사 대상 추가

조사 중 새 API·화면·테이블을 발견하면 lead가 새 파일의 종류·단계·상대 경로·제목을 담은 JSON을 작성하고 아래 명령으로 등록한다. 지난 단계에 추가하려면 먼저 rework한다. 등록 후 폴더 INDEX가 갱신된다.

~~~text
python flow.py add --run 작업폴더 --record 새대상.json --actor document-lead
~~~
