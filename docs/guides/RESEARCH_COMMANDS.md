# 조사 실행 명령

Python 3.12에서 `document.py research`로 조사 계획, 실행, 상태 확인과 재개를 관리한다. 제품마다 명령을 복제하지 않고 등록된 회사·제품·환경 설정을 읽는다.

## 조사 흐름

| 순서 | 단계 | 담당 | 산출물 |
| --- | --- | --- | --- |
| 1 | 범위 확인 | 총괄 | 목적·대상·제외 범위 |
| 2 | 대상 목록 조사 | 조사 책임자 | 코드·화면·API·데이터 목록 |
| 3 | 구조 조사 | 아키텍처 담당 | 시스템 구성·데이터 흐름 |
| 4 | 화면 동작 조사 | 화면 조사 담당 | 페이지별 동작·필터·권한·오류 |
| 5 | 데이터 조사 | 데이터 조사 담당 | API·지표·테이블별 Markdown |
| 6 | 조사 정합성 검토 | 조사 책임자 | 불일치·미확인 항목·담당자 |

실제 담당자, 산출물 경로와 필요한 유형은 회사 workflow와 제품 plan을 따른다. 본문은 분류된 폴더의 Markdown에 작성하고 INDEX로 연결한다. 상태·해시·출처 등록은 관리 파일에 보관한다.

## 계획과 실행

~~~powershell
# 읽기 전용: 대상, 담당, 산출물과 실행 조건 확인
python document.py research plan --product demo --environment local

# 새 조사 작업 생성 및 현재 단계 실행 계획 확인
python document.py research run --product demo --environment local

# 승인된 AI 실행기를 설정한 뒤 현재 단계 실행
python document.py research run --product demo --environment local --execute
~~~

`demo`는 가상 예제다. 실제 제품은 `config/catalog.json`에 등록한다. plan은 작업 폴더를 만들지 않는다. run은 새 작업 폴더를 만들지만 기본값으로 AI·브라우저·DB에 접속하지 않는다. 실행 결과에 표시된 작업 폴더 경로를 이후 `--run`에 전달한다.

AI 실행기는 `config/ai/execution.json`의 enabled와 담당자별 command 설정을 사용한다. 공급자 연결이 없다면 조사 완료로 표시하지 않는다. 자세한 연결 계약은 [AI 실행 인터페이스](AI_EXECUTION.md)를 따른다.

## 상태 확인과 중단 후 재개

~~~powershell
python document.py research status --run 작업폴더
python document.py research resume --run 작업폴더
python document.py research resume --run 작업폴더 --execute
~~~

resume은 해당 작업에 저장된 제품·환경으로 현재 조사 단계만 다시 실행한다. 이전 기록을 지우거나 단계 승인을 복사하지 않는다. 기존 작성 내용을 기반으로 현재 담당 파일을 다시 작업하므로 실패 기록과 미확인 내용을 먼저 확인한다.

이 명령으로 생성한 `workspaces/{회사}/{제품}/{실행}` 작업만 재개한다. 제품·환경 바인딩이 없는 과거 `flow.py init` 작업이나 저장소 밖의 테스트 사본을 자동으로 가져오지 않는다. 그런 작업에는 기존 개별 명령을 사용한다.

조사 단계가 끝나고 집필 단계에 들어간 작업을 이 명령으로 재실행하지 않는다. 승인된 내용을 고쳐야 할 때는 기존 `flow.py rework` 절차로 해당 단계의 승인과 후속 승인을 무효화한 뒤 재개한다.

## 화면·DB 근거 수집

~~~powershell
# 브라우저 캡처를 명시적으로 수집한 뒤 현재 AI 단계 실행
python document.py research resume --run 작업폴더 --execute --collect

# 환경에 설정된 읽기 전용 PostgreSQL 조회도 함께 실행
python document.py research resume --run 작업폴더 --execute --collect --with-db
~~~

`--collect`에는 `--execute`가 필요하고 `--with-db`에는 `--collect`가 필요하다. 옵션이 없으면 기존 근거를 재사용하며 캡처·DB 조회를 자동 반복하지 않는다. 로그인 정보와 DB 비밀번호는 설정에 지정된 환경변수로 제공한다. 값은 명령행에 쓰지 않는다.

실제 수집은 기존 Playwright 캡처 설정과 읽기 전용 PostgreSQL 수집기를 사용한다. 성공한 수집 파일을 조사 근거로 등록한다. 부분 실패는 실패·미확인으로 남기며 전체 조사 완료로 간주하지 않는다. 캡처 이미지에 개인정보가 들어갈 수 있으므로 [캡처 설정](CAPTURE_SETTINGS.md)의 마스킹 규칙을 적용한다.

## 다음 단계로 진행

이 명령은 조사 실행과 승인을 분리한다. AI가 작업을 끝내도 자동으로 다음 단계에 넘어가지 않는다.

~~~powershell
# 담당자의 실제 검토 후 기존 게이트 명령 사용
python flow.py advance --run 작업폴더 --actor 담당자ID
python document.py research status --run 작업폴더
~~~

출처·필수 내용·상태·기존 승인 해시가 유효해야 단계가 진행된다. 내용의 사실 여부는 독립 검토한다. 조사 6단계 이후의 개요·집필·사실검증·리뷰·서식·전달은 기존 문서 workflow를 따른다. `research resume`이 이를 자동 승인하지 않는다.
