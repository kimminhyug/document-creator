# AI 실행 인터페이스

## 역할과 실행기 분리

roles와 제품 workflow plan은 담당자를 정한다. config/ai/execution.json은 실제 프로세스를 연결한다. 특정 모델·서비스를 기본값으로 호출하지 않는다.

~~~json
{
  "enabled": false,
  "workers": 2,
  "timeout_seconds": 300,
  "default": {"command": [], "pass_env": []},
  "roles": {},
  "agents": {}
}
~~~

명령 선택 우선순위는 agents의 담당자 이름 → roles의 역할 이름 → default다. command는 셸 문자열이 아니라 인자 배열이며 셸을 실행하지 않는다. 예를 들어 회사에서 구현한 래퍼를 `["runtime:python", "{root}/.local/company_agent.py"]`로 지정할 수 있다. 중괄호 자리표시자는 root, run, artifact, task를 지원한다. runtime:python은 로컬 런타임 설정의 python 경로다.

API 키 등이 필요하면 pass_env에 환경변수 이름만 지정한다. 부모 환경의 다른 인증값은 자동 상속하지 않는다. 실제 공급자 SDK나 CLI의 계약을 이 프로토콜로 변환하는 래퍼는 사용 환경에 맞게 연결한다.

## 요청과 응답

실행기는 stdin으로 UTF-8 JSON 요청을 받는다. protocol, workspace, artifact, metadata, prompt, index, allowed_write_paths가 포함된다. INDEX.md와 정책을 읽고 자기 MD 및 대응 관리 JSON만 수정한다.

stdout 응답은 아래 JSON 한 개다. 원문 모델 응답을 로그에 출력하지 않는다.

~~~json
{"status": "completed"}
~~~

completed는 프로세스 작업 종료를 뜻하며 내용 검증 통과가 아니다. 파일은 별도로 필수 항목·출처·소유권·상태 검사한다. 미확정이면 단계 진행을 막는다.

## 실행과 실패

~~~text
python ai_runner.py --run 작업폴더
python ai_runner.py --run 작업폴더 --execute
python ai_runner.py --run 작업폴더 --execute --advance
python ai_runner.py --run 작업폴더 --execute --until-complete
~~~

기본 명령은 실행 계획만 보여준다. 실제 실행에는 enabled=true와 --execute가 모두 필요하다. 동시에 여러 파일을 작업할 수 있으며 각 담당자에게 독립 작업사본을 제공한다. 해당 담당자의 MD와 관리 JSON만 원래 작업에 반영한다.

응답 크기와 실행 시간을 제한하고 stdout/stderr 원문을 영구 기록하지 않는다. 결과는 agent-runs의 result.json에 상태·담당 파일·실패 종류만 보관한다. 실패 시 임의 자동 재시도하지 않는다. 기존 작성 내용과 오류를 확인하고 같은 명령을 다시 실행하거나 lead가 rework로 앞 단계에 돌린다.

OS 권한 격리는 제공하지 않는다. 승인된 실행기만 연결하고 OS 계정·파일 권한·외부 서비스 허용 범위를 별도로 관리한다. 생성기는 실제 공급자 접근권한이나 비용 승인을 대신하지 않는다.

## 완료 판정

--until-complete도 게이트를 우회하지 않는다. 실제 출력과 형식별 검수 증거가 없으면 서식·전달 단계는 완료되지 않는다. 실물 DB 조회, Word/Excel 화면 확인처럼 환경이 필요한 작업을 수행하지 못했으면 미검증으로 유지한다.
