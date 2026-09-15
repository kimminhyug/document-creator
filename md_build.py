"""Compile classified Markdown into a disposable layout model, then company render."""
import argparse
import tempfile
import re
from pathlib import Path
from collector.config import ROOT, read, need, scoped
from creator import build, write_json, digest
from company_build import settings
from flow import evidence_ids, unchanged
from md_contract import validate_artifact, blocks, metadata_path


def document_blocks(body, base, run):
    """Keep the required source container out of the reader's heading outline."""
    visible, in_content, fenced = [], False, None
    for line in body.splitlines():
        marker = re.match(r' {0,3}(`{3,}|~{3,})', line)
        if marker and not fenced:
            fenced = marker[1]
            visible.append(line)
            continue
        if fenced:
            visible.append(line)
            if re.fullmatch(r' {0,3}' + re.escape(fenced[0]) + '{' + str(len(fenced)) + r',}\s*', line):
                fenced = None
            continue
        if line == '## 내용':
            in_content = True
            continue
        if line.startswith('## '):
            in_content = False
        if in_content and re.match(r'#{3,5} ', line):
            line = line[1:]
        visible.append(line)
    return blocks('\n'.join(visible), base, run)


def readable_references(items, base, run, targets, web_links=None):
    """Printed documents use document/section names, never workspace file paths.

    Code examples are literal. Web links retain their full address for print and
    are made clickable by output adapters. Cross-document references are textual
    because each document can be exported independently to an unrelated folder.
    """
    def replace(match):
        label, target = match[1], match[2]
        if target.startswith(('http://', 'https://')):
            from urllib.parse import urlsplit
            url = urlsplit(target)
            need(url.hostname and not url.username and not url.password, 'unsafe public URL')
            from inline_links import validate_web_links
            validate_web_links([target])
            if web_links is not None:web_links.add(target)
            return label if label == target else f'{label} ({target})'
        if target.startswith('#'):
            return label + ' 절 참조'
        file = target.split('#', 1)[0]
        resolved = scoped(run, str(base.relative_to(run) / file))
        need(resolved in targets, 'reference target is not a registered document')
        title = targets[resolved]
        return title if label == title else f'{label} ({title})'
    def render(value):
        # Inline code, like fenced code, is an example rather than a reference.
        parts = re.split(r'(`+[^`]*`+)', value)
        return ''.join(part if part.startswith('`') else re.sub(r'(?<!!)\[([^\]]+)\]\(([^)]+)\)', replace, part) for part in parts)
    for item in items:
        if item['type'] in ('code', 'image'):
            continue
        if item['type'] == 'table':
            item['headers'] = [render(v) for v in item['headers']]
            item['rows'] = [[render(v) for v in row] for row in item['rows']]
        else:
            item['text'] = render(item['text'])
    return items


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
    web_links = set()
    from md_contract import parse
    document_names = {a['document_type']: parse(run / a['path'])[0].get('title', a['title']) for a in state['artifacts'] if a['kind'] == 'document_index'}
    targets = {(run / a['path']).resolve(): document_names[a['document_type']] + (' — ' + a['title'] if a['kind'] == 'document_section' else '') for a in state['artifacts'] if a.get('document_type') and a['kind'] in ('document_index', 'document_section')}
    for source in read(run / "sources/evidence-index.json"):
        content["sources"].append({"id": source["id"], "title": source["original_name"], "locator": source["path"]})
    for record in records:
        if record["kind"] != "document_section":
            continue
        meta, body = validate_artifact(run, record, state, source_ids, allow_pending=True)
        content["sections"].append({"id": record["section_id"], "title": record["title"], "status": meta["status"], "sources": meta["sources"], "reason": meta.get("reason", "조사 또는 집필 미완료"), "owner": meta["author"], "blocks": document_blocks(body, (run / record["path"]).parent, run) if meta["status"] == "confirmed" else []})
        readable_references(content['sections'][-1]['blocks'], (run / record['path']).parent, run, targets, web_links)
    content['web_links'] = sorted(web_links)
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
