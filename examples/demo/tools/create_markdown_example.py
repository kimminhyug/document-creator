"""Migrate synthetic table example to classified Markdown, without approving workflow."""
import json
import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
from flow import initialize, register_source
from md_contract import write_artifact
from indexes import refresh
from creator import read_json, write_json

run = initialize("demo")
register_source(run, "example-source", ROOT / "examples/demo/content/table-spec.json")
state = read_json(run / "state.json")
example = read_json(ROOT / "examples/demo/content/table-spec.json")
sections = {s["id"]: s for s in example["sections"]}
for record in state["artifacts"]:
    if record.get("document_type") != "table_spec":
        continue
    meta = {"id": record["id"], "kind": record["kind"], "company": "demo", "product": "demo", "status": "confirmed", "sources": ["example-source"], "author": record["agent"]}
    if record["kind"] == "document_index":
        meta.update(title=example["title"], summary=example["summary"], version="0.2", example=True)
        body = "# " + example["title"] + "\n\n## 문서 목적\n\n" + example["summary"] + "\n\n## 목차\n\n"
        for sid, section in sections.items():
            body += f"- [{section['title']}](sections/{sid.replace('_', '-')}.md)\n"
    else:
        section = sections[record["section_id"]]
        record["title"] = section["title"]
        body = "# " + section["title"] + "\n\n## 내용\n\n"
        for block in section["blocks"]:
            if block["type"] == "table":
                body += "| " + " | ".join(block["headers"]) + " |\n"
                body += "| " + " | ".join("---" for _ in block["headers"]) + " |\n"
                for row in block["rows"]:
                    body += "| " + " | ".join(row) + " |\n"
            elif block["type"] == "note":
                body += "> [!" + {"info": "NOTE", "warning": "WARNING", "example": "EXAMPLE"}[block["role"]] + "]\n> " + block["text"] + "\n"
            else:
                body += block["text"] + "\n"
            body += "\n"
        body += "## 관련 참조\n\n문서 형식을 설명하기 위한 가상 예제입니다. 실제 DB 검증 결과가 아닙니다.\n"
    write_artifact(run / record["path"], meta, body)
write_json(run / "state.json", state)
refresh(run)
print(run)
