import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
from creator import write_json, read_json

policy = read_json(ROOT / "policies/artifacts.json")
workflow = read_json(ROOT / "workflows/senior-document-team.json")
artifacts = []
names = {"scope": "작업 범위", "inventory": "조사 대상 목록", "architecture": "구조와 데이터 흐름", "page": "성능 요약 화면 조사", "api": "성능 조회 API 조사", "metric": "Availability 지표 조사", "table": "설비 상태 이력 조사", "reconcile": "근거 불일치 정리", "outline": "문서별 목차와 분담", "fact_check": "사실 검증", "review": "독립 문서 리뷰", "style_check": "회사 서식 검증", "publish": "최종 전달 기록"}
for stage in workflow["stages"]:
    for kind in stage["kinds"]:
        if kind.startswith("document_"):
            continue
        artifacts.append({"id": kind.replace("_", "-") + "-001", "kind": kind, "stage": stage["id"], "path": policy["kinds"][kind]["prefix"] + kind.replace("_", "-") + "-001.md", "title": names[kind]})
for template in (ROOT / "templates").glob("*.json"):
    contract = read_json(template)
    doc_type = contract["id"]
    artifacts.append({"id": doc_type.replace("_", "-") + "-index", "kind": "document_index", "stage": "draft", "path": f"documents/{doc_type}/INDEX.md", "title": contract["name"], "document_type": doc_type})
    for section_id in contract["required_sections"]:
        artifacts.append({"id": doc_type.replace("_", "-") + "-" + section_id.replace("_", "-"), "kind": "document_section", "stage": "draft", "path": f"documents/{doc_type}/sections/{section_id.replace('_', '-')}.md", "title": section_id, "document_type": doc_type, "section_id": section_id})
target = ROOT / "examples/demo/products/demo/workflows/default.json"
if target.exists():
    raise SystemExit("Refusing overwrite")
write_json(target, {"id": "default", "artifacts": artifacts})
