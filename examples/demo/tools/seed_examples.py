"""Create the repository's example/config files; explicit authoring helper, not runtime."""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def save(path, data):
    target = ROOT / path
    if target.exists():
        raise SystemExit(f"Refusing overwrite: {target}")
    target.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


templates = {
    "table_spec": ("테이블 명세서", ["overview", "catalog", "columns", "constraints", "examples", "references"]),
    "user_manual": ("사용자 매뉴얼", ["overview", "environment", "features", "usage", "troubleshooting", "references"]),
    "functional_spec": ("기능 명세서", ["overview", "features", "rules", "behavior", "acceptance", "references"]),
    "api_spec": ("API 명세서", ["overview", "catalog", "common", "request", "response", "errors", "references"]),
    "metric_spec": ("지표 계산식 명세서", ["overview", "catalog", "definition", "formula", "data_mapping", "examples", "references"]),
}
for identifier, (label, sections) in templates.items():
    save(f"templates/{identifier}.json", {"id": identifier, "name": label, "version": "0.1", "required_sections": sections, "validation_scope": "section presence, block shape, references, source and pending status; detailed domain validation remains manual"})

save("themes/blue-office.json", {
    "id": "blue-office", "version": "0.1", "font_family": "Malgun Gothic",
    "page_width_mm": 210, "page_height_mm": 297, "margin_mm": 22,
    "body_pt": 10.5, "title_pt": 28, "heading_pt": 16, "table_pt": 9,
    "line_spacing": 1.5,
    "colors": {"text": "#202D3A", "muted": "#5D6E80", "accent": "#246BCE", "table_fill": "#DCEAF9", "table_text": "#152638", "border": "#D6E0EA", "background": "#FFFFFF"},
    "notes": {
        "info": {"label": "참고", "fill": "#EEF5FF", "marker": "#246BCE"},
        "warning": {"label": "확인 필요", "fill": "#FFF5E5", "marker": "#BC791D"},
        "example": {"label": "예시", "fill": "#F0F4F8", "marker": "#697F99"},
    },
    "header": {"left": "{organization}", "right": "{id} · {version}"},
    "footer": {"left": "{classification}"},
    "ending": {"enabled": True, "title": "문서 문의", "text": "{organization}\n{contact}\n문서 ID {id}\n문서 내용 변경 시 관련 명세를 함께 확인하세요."},
})
save("examples/demo/content/project.json", {"name": "설비 모니터링 예제", "organization": "문서 자동화 예제", "contact": "프로젝트 문서 담당자", "classification": "예제 문서"})


def p(s):
    return {"type": "paragraph", "text": s}


def table(headers, rows):
    return {"type": "table", "headers": headers, "rows": rows}


def sec(identifier, title, blocks):
    return {"id": identifier, "title": title, "status": "confirmed", "sources": ["SRC-01"], "blocks": blocks}


sample = {
    "id": "DATA-DEMO-001", "type": "table_spec", "title": "설비 상태 이력 테이블 명세서", "version": "0.1", "example": True,
    "summary": "설비 기본 정보와 상태 이력의 구조를 설명합니다. 컬럼 의미와 시간 경계, 관계를 확인하여 데이터 조회와 계산에 활용할 수 있습니다.",
    "sources": [{"id": "SRC-01", "title": "테이블 명세서 작성 가이드의 가상 설계 사례", "locator": "rules/테이블_명세서_작성_가이드.md / 6절과 7절"}],
    "sections": [
        sec("overview", "문서 개요", [p("이 문서는 가상의 설비 데이터를 사용한 테이블 명세서입니다. 실제 DB 구조나 적용 결과를 의미하지 않습니다."), {"type": "note", "role": "info", "text": "한 행의 의미와 NULL의 의미를 먼저 확인하세요. 계산 변수와 DB 컬럼은 별도로 관리합니다."}]),
        sec("catalog", "테이블 목록", [table(["테이블", "용도", "한 행의 의미"], [["equipment", "설비 기본 정보", "설비 한 대"], ["equipment_state_history", "설비 상태 이력", "설비 한 대의 연속된 상태 구간"]])]),
        sec("columns", "컬럼 정의", [p("equipment_state_history의 가상 컬럼 정의입니다. TIMESTAMP의 실제 선언과 시간대 지원은 DBMS 결정 후 확정합니다."), table(["컬럼", "타입", "NULL", "의미"], [["history_id", "BIGINT", "불가", "상태 구간의 고유 ID"], ["equipment_id", "VARCHAR(20)", "불가", "설비 ID. equipment를 참조"], ["state", "VARCHAR(20)", "불가", "RUNNING / READY / DOWN / UNKNOWN"], ["start_at", "TIMESTAMP", "불가", "상태 시작 시각. UTC, 시작 포함"], ["end_at", "TIMESTAMP", "허용", "종료 시각. NULL은 미확정, 종료 제외"], ["received_at", "TIMESTAMP", "불가", "마지막 수신 또는 정정 반영 시각"]])]),
        sec("constraints", "키와 제약조건", [table(["구분", "기준", "적용 위치"], [["PK", "history_id는 고유하며 NULL 불가", "DB 제약 설계"], ["FK", "equipment_id가 equipment에 존재", "DB 제약 설계"], ["시간 순서", "종료가 있으면 시작보다 늦어야 함", "DB CHECK 설계"], ["상태 겹침", "같은 설비 구간의 겹침 검출", "별도 품질 검사"]]), {"type": "note", "role": "warning", "text": "PK와 FK를 통과해도 시간 구간의 누락이나 겹침이 없다는 뜻은 아닙니다."}]),
        sec("examples", "데이터 예시", [table(["설비", "상태", "UTC 구간"], [["OHT-01", "RUNNING", "2026-09-15 00:00 ~ 01:00"], ["OHT-01", "DOWN", "2026-09-15 01:00 ~ 01:15"], ["OHT-01", "READY", "2026-09-15 01:15 ~ 종료 미확정"]]), {"type": "note", "role": "example", "text": "KST 10시 경계는 DOWN 구간에 포함됩니다. READY의 종료 미확정을 현재까지 정상 상태였다는 의미로 단정하지 않습니다."}]),
        sec("references", "관련 문서", [p("지표 계산의 포함 구간과 상태 분류는 지표 계산식 명세서에서 정의합니다. API 응답 필드는 API 명세서와 연결합니다.")]),
    ],
}
save("examples/demo/content/table-spec.json", sample)

# These are visibly pending authoring starters, not fabricated complete manuals.
for identifier, (label, sections) in templates.items():
    if identifier == "table_spec":
        continue
    draft = {"id": identifier.upper() + "-STARTER", "type": identifier, "title": label + " 작성 시작본", "version": "0.1", "summary": "확인한 자료를 입력하고 미확정 항목을 담당자가 검토합니다.", "sources": [{"id": "SRC-01", "title": "작성 규칙", "locator": "rules/"}], "sections": [{"id": s, "title": s, "status": "pending", "owner": "문서 담당자", "reason": "실제 자료 입력 필요", "sources": [], "blocks": []} for s in sections]}
    save(f"examples/demo/content/{identifier}-starter.json", draft)
