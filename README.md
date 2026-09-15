# Document Creator

여러 제품에서 사용하는 회사 표준 문서 생성기입니다. **조사와 집필 원본은 분류된 Markdown**, Word·Excel·HTML·PDF는 파생 출력입니다. Python 3.12를 기준으로 합니다.

## 먼저 볼 파일

- [전체 폴더 안내](INDEX.md)
- [디렉토리·인터페이스 정책](docs/policies/INTERFACE_POLICY.md)
- [문서팀 역할과 12단계 흐름](docs/policies/DOCUMENT_TEAM.md)
- [본문 작성 규칙](docs/policies/WRITING_STANDARD.md)
- [캡처 설정](docs/guides/CAPTURE_SETTINGS.md)
- [AI 실행 연결](docs/guides/AI_EXECUTION.md)
- [검증 결과와 제한](docs/development/STATUS.md)

## 실제 정책과 데모 구분

| 위치 | 의미 |
| --- | --- |
| rules/ | 합의한 5종 문서 작성 가이드 |
| policies/, workflows/, roles/ | 공통 분류·단계·역할 계약 |
| templates/ | 문서 유형별 최소 필수 절 검사 |
| themes/, profiles/ | 공통 출력 스타일·캡처 프로필 |
| config/companies/, config/products/ | 실제 회사·제품 설정을 등록할 위치. 현재 비어 있음 |
| config/catalog.json | 제품/회사 설정의 명시적 위치 목록 |
| examples/demo/ | 모든 테스트 회사·제품·가상 내용. 실제 회사 정책으로 간주하지 않음 |
| docs/policies/, docs/guides/, docs/development/ | 운영 정책 / 사용법 / 개발 이력 |
| workspaces/ | 실행마다 생성되는 분류된 조사·본문·검토 MD. Git 제외 |
| output/ | 캡처·조회·파생 문서. Git 제외 |
| .local/ | 로컬 도구 경로·인증 파일. Git 제외 |

`demo`는 가상 테스트 제품입니다. 새 제품은 config/ 아래에 만들고 catalog에 등록합니다. 생성기에 제품 이름이나 계정을 하드코딩하지 않습니다. 각 폴더의 INDEX.md는 다음 탐색 위치를 안내합니다.

## 설치와 환경

Python 3.12 환경에서 requirements.txt의 라이브러리를 사용합니다. 자동 설치는 하지 않습니다. config/runtime.example.json을 .local/runtime.json으로 복사하고 사용할 도구의 실제 경로를 입력합니다.

- Word: python-docx. Word 시각 검수에는 별도 Word/LibreOffice 렌더러가 필요합니다.
- Excel: openpyxl. 내용·시트·스타일 구조를 검사합니다.
- HTML: 추가 패키지 없이 생성하며 이미지를 파일 안에 포함합니다.
- PDF: ReportLab과 허용된 실제 폰트 파일을 사용합니다. Word 변환본이 아닙니다.
- 캡처: Node.js + Playwright + Chromium. Python이 별도 브라우저 프로세스를 조정합니다.
- PostgreSQL: psql과 운영자가 만든 읽기 전용 계정. 접속 정보는 환경변수로 제공합니다.

설치된 패키지 버전은 requirements.txt에 기록했습니다. 폰트·브라우저·외부 실행기는 저장소에 포함하지 않습니다. `python tools/doctor.py`로 환경을 확인합니다. 특정 기능을 사용하지 않으면 해당 외부 도구는 선택 사항입니다.

## 기본 실행

아래 python은 설정된 Python 3.12 실행 파일입니다.

~~~text
python flow.py init --product demo
python flow.py source --run 작업폴더 --source-id request --file 요청서.md
python flow.py tasks --run 작업폴더
python ai_runner.py --run 작업폴더
python md_build.py --run 작업폴더 --type table_spec --formats docx xlsx html pdf
python indexes.py
python -m unittest discover -s tests -v
~~~

AI 실행은 기본 dry-run입니다. config/ai/execution.json에 실행기와 환경변수 이름을 설정한 뒤 --execute를 사용합니다. --until-complete는 단계별 검사 통과 시에만 다음 단계로 이동합니다. 실패·미확정이면 멈추고 보고서를 남깁니다. 사용자의 모델·서비스를 임의로 선택하지 않습니다.

가상 Markdown 예제는 `python examples/demo/tools/create_markdown_example.py`로 새 작업 폴더에 만듭니다. 원본 MD는 사람이 읽는 내용만 포함합니다. ID·출처 연결·상태는 .metadata/의 대응 JSON에서 관리하며 최종 문서에 출력하지 않습니다.

## 출력·검토

회사 테마는 표지, 저작권 페이지, 목차, 머릿글, 바닥글, 마지막 페이지, 역할별 폰트·크기·굵기, 표 헤더 배경·여백·테두리를 설정합니다. AI 본문이 스타일을 덮어쓰지 않습니다.

출력 성공은 승인과 다릅니다. 미확정 내용을 담은 검토본을 만들 수 있지만 사실 검증·독립 리뷰·서식 검수·전달 게이트는 따로 통과해야 합니다. 최종 전달에는 실제 출력 파일, 해시, 형식별 검수 기록이 필요합니다. 상세 업무 사실은 사람이 또는 독립 에이전트가 검증하며 필수 절 검사만으로 진위를 보장하지 않습니다.

## 보안과 Git

인증값·세션·DB 결과·캡처·생성 문서·로컬 경로 설정은 Git에 포함하지 않습니다. 환경 설정에는 로그인/DB 환경변수의 이름만 씁니다. 최초 또는 후속 커밋 전에 `python tools/check_staged.py`로 staged 파일을 확인합니다. 정규식 검사는 비밀 검토를 보조하며 모든 비밀 형태를 찾아낸다는 보장은 없습니다.
