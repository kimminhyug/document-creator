# 제품별 Playwright 캡처와 PostgreSQL 조회

## 실행 환경

Python 3.12가 설정 검증·병렬 프로세스 관리·결과 기록을 담당한다. 브라우저 엔진은 이미 설치된 Node Playwright를 얇은 worker로 호출한다. 새 Python Playwright 패키지는 설치하지 않았다.

.local/runtime.json에 node / playwright_module / chromium / psql 절대 경로를 설정한다. 버전이 다른 Playwright 브라우저는 실제 호환 검증이 필요하다. 현재 설치된 Chromium으로 로컬 fixture 캡처를 검증했다.

## 제품과 환경

제품 설정에는 URL·준비 완료 selector·마스크·촬영 방식만 기록하고 인증정보는 환경 변수로 연결한다. DB와 인증 변수명은 DOC__제품ID__환경ID 접두사로 제한한다. 예: DOC__DEMO__LOCAL_AUTH_STATE.

~~~text
python collect.py --product demo --environment local --validate-only
python examples/demo/tools/demo_capture_server.py
python collect.py --product demo --environment local
python collect.py --product demo --environment local --with-db
~~~

기본 실행은 DB에 접속하지 않는다. --with-db를 명시해야 조회한다. demo의 localhost URL은 실제 제품이 아닌 테스트 fixture다.

## 캡처 정책

- workers 수만큼 별도 Node/브라우저 프로세스를 띄워 페이지를 분할한다.
- 각 페이지는 별도 browser context를 사용한다. 사용자 브라우저 프로필을 직접 열지 않는다.
- viewport: 화면 1장, segments: 겹침을 유지하며 세로 스크롤 분할, element: 지정 영역만 캡처.
- ready_selector 표시와 폰트 준비를 확인한다.
- 설정한 마스크 selector가 하나도 없으면 실패 처리한다.
- 허용 origin 외의 페이지·리디렉션·하위 자원 요청은 차단한다. 필요한 CDN origin은 환경 설정에 명시한다.
- 임의 JavaScript·자동 저장/삭제 버튼 조작을 설정으로 실행하지 않는다. 페이지 자체의 네트워크 요청이 서버 부작용을 전혀 만들지 않는다는 보장은 아니다.
- 시간 제한·분할 수 제한·프로세스 종료 시 자식 브라우저 정리를 적용한다.
- 결과는 output/collection/{product}/{environment}/{run}에 저장하고 제품·회사 ID를 manifest에 남긴다.
- 실패는 partial_failure 또는 failed로 표시하며 성공한 자료만 명시적으로 참조한다. 이미지 생성은 시각 검토 통과와 다르다.

내부 스크롤 컨테이너·클릭 후 팝업·동적 높이 무한 스크롤은 현재 범위 밖이다. segments는 문서 전체의 세로 스크롤이다.

## PostgreSQL 조회 전용 정책

자유 SQL은 입력받지 않는다. 승인 schema/table/column 목록과 구조화된 조건으로 SELECT를 생성한다. 임의 함수·SQL 파일·세미콜론 명령을 전달하는 인터페이스는 없다.

계층별 제한:

1. 필요한 테이블/뷰만 DBA가 승인.
2. 서버 전용 계정에 필요한 SELECT만 부여. 쓰기 권한·SUPERUSER·CREATEDB·CREATEROLE·REPLICATION·BYPASSRLS 계정 사용 금지.
3. 시작 시 read-only 기본값 + READ ONLY 트랜잭션.
4. 현재 계정의 고권한과 대상 관계의 테이블/컬럼 쓰기 권한을 먼저 검사. 해당되면 실제 조회 전 중단.
5. 행 수·셀 문자 수·실행 시간·락 대기·프로세스 대기 제한.
6. 종료 시 ROLLBACK. psql -X로 사용자 초기화 스크립트 제외, -w로 비밀번호 대화상자 차단.

READ ONLY는 모든 파일 쓰기나 함수의 외부 부작용까지 막는 보안 샌드박스가 아니다. 승인 View·사용자 정의 타입·함수는 DBA가 검토해야 하며, 전용 계정의 권한이 최종 방어선이다. 도구는 계정 생성·권한 변경·스키마 변경을 수행하지 않는다.

필요 환경 변수 예:

~~~text
DOC__DEMO__LOCAL_HOST
DOC__DEMO__LOCAL_PORT
DOC__DEMO__LOCAL_DATABASE
DOC__DEMO__LOCAL_USER
DOC__DEMO__LOCAL_PASSWORD 또는 DOC__DEMO__LOCAL_PASSFILE
DOC__DEMO__LOCAL_SSLROOTCERT (필요 시)
~~~

기본 TLS는 verify-full이다. 비밀번호는 명령행·설정·manifest에 기록하지 않는다. 기존 다른 제품 PG 환경 변수는 제거한 별도 프로세스 환경으로 접속한다.

조회 결과는 문서 조사용 텍스트이며 max_cell_chars에서 잘리고 max_rows로 제한될 수 있다. 타입을 보존한 전체 데이터 export가 아니다. max_cell_chars·row_limit_reached를 결과에 기록한다. 캡처와 DB 조회는 서로 다른 시각이며 동일 트랜잭션 스냅샷이라고 주장하지 않는다.

실제 서버 연결은 접속 정보가 없어 아직 미검증이다. 로컬 테스트는 SQL 생성·차단 정책만 검증하며 실제 서버에서 쓰기 차단이 확인됐다고 보고하지 않는다.

## 공식 근거

- [Playwright page screenshot 및 mask](https://playwright.dev/docs/api/class-page#page-screenshot)
- [PostgreSQL READ ONLY 트랜잭션과 제한](https://www.postgresql.org/docs/current/sql-set-transaction.html)
- [PostgreSQL 권한 종류](https://www.postgresql.org/docs/current/sql-grant.html)
