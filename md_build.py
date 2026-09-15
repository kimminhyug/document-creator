"""Compile classified Markdown into a disposable layout model, then company render."""
import argparse
import tempfile
from pathlib import Path
from collector.config import ROOT, read, need, scoped
from creator import build, write_json, digest
from company_build import settings
from flow import evidence_ids, unchanged
from md_contract import validate_artifact, blocks, metadata_path


def compile_document(run, document_type):
    state = read(run / "state.json")
    unchanged(run, state)
    source_ids = evidence_ids(run)
    records = [a for a in state["artifacts"] if a.get("document_type") == document_type]
    indexes = [a for a in records if a["kind"] == "document_index"]
    need(len(indexes) == 1, "document requires one registered index.md")
    index_meta, index_body = validate_artifact(run, indexes[0], state, source_ids, allow_pending=True)
    need(index_meta["status"] == "confirmed", "document index must be written")
    for key in ("title", "version", "summary"):
        need(isinstance(index_meta.get(key), str) and index_meta[key], f"index metadata needs {key}")
    content = {"id": indexes[0]["id"], "type": document_type, "title": index_meta["title"], "version": index_meta["version"], "summary": index_meta["summary"], "example": index_meta.get("example", False), "sources": [], "sections": []}
    content["public_references"] = index_meta.get("public_references", [])
    for source in read(run / "sources/evidence-index.json"):
        content["sources"].append({"id": source["id"], "title": source["original_name"], "locator": source["path"]})
    for record in records:
        if record["kind"] != "document_section":
            continue
        meta, body = validate_artifact(run, record, state, source_ids, allow_pending=True)
        content["sections"].append({"id": record["section_id"], "title": record["title"], "status": meta["status"], "sources": meta["sources"], "reason": meta.get("reason", "조사 또는 집필 미완료"), "owner": meta["author"], "blocks": blocks(body, (run / record["path"]).parent, run) if meta["status"] == "confirmed" else []})
    return content, state


def render(run, document_type, formats):
    content, state = compile_document(run, document_type)
    company, theme, project, contract = settings(state["product"], document_type)
    need(company["id"] == state["company"], "workspace company mismatch")
    with tempfile.TemporaryDirectory() as temporary:
        intermediate = Path(temporary) / "layout-input.json"
        write_json(intermediate, content)
        output = build(intermediate, contract, project, theme, ROOT / ".local/runtime.json",
                       ROOT / "output/documents" / company["id"] / state["product"] / state["run_id"], formats)
        report = read(output / "manifest.json")
        report["markdown_sources"] = [{"path": a["path"], "sha256": digest(run / a["path"])} for a in state["artifacts"] if a.get("document_type") == document_type]
        report["metadata_sources"] = [{"path": metadata_path(run / a["path"], run).relative_to(run).as_posix(), "sha256": digest(metadata_path(run / a["path"], run))} for a in state["artifacts"] if a.get("document_type") == document_type and metadata_path(run / a["path"], run).exists()]
        report["workspace"] = str(run)
        report["workflow_status"] = "preview; output generation does not pass publish gate"
        write_json(output / "manifest.json", report)
        return output


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--run", required=True, type=Path)
    p.add_argument("--type", required=True)
    p.add_argument("--formats", nargs="+", choices=["pdf", "docx", "html", "xlsx"], default=["pdf"])
    args = p.parse_args()
    print(render(args.run.resolve(), args.type, args.formats))
