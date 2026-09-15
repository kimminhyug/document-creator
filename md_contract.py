"""Markdown source interface: stable artifact IDs + source/provenance sidecars."""
import json
import re
from pathlib import Path
from collector.config import ROOT, need, scoped, read

META = re.compile(r"\A<!-- docmeta: (\{[^\n]*\}) -->\r?\n")


def parse(path):
    source = Path(path).read_text(encoding="utf-8-sig")
    match = META.match(source)
    if match:  # Read-only compatibility for historical workspaces.
        return json.loads(match[1]), source[match.end():]
    sidecar = metadata_path(path)
    need(sidecar.is_file(), "Markdown metadata sidecar required")
    return read(sidecar), source


def metadata_path(path, run=None):
    path = Path(path).resolve()
    if run is None:
        run = next((p for p in path.parents if (p / '.metadata').is_dir()), None)
    need(run is not None, "workspace metadata directory required")
    run = Path(run).resolve()
    need(path.is_relative_to(run), "artifact outside workspace")
    return scoped(run, '.metadata/' + path.relative_to(run).as_posix() + '.json')


def write_artifact(path, meta, body, run=None):
    path = Path(path)
    sidecar = metadata_path(path, run)
    sidecar.parent.mkdir(parents=True, exist_ok=True)
    sidecar.write_text(json.dumps(meta, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    path.write_text(body, encoding='utf-8')


def validate_artifact(run, record, state, source_ids, allow_pending=False):
    path = scoped(run, record["path"])
    meta, body = parse(path)
    policy = read(ROOT / "policies/artifacts.json")
    for key in policy["metadata_fields"]:
        need(key in meta, f"missing metadata: {key}")
    for key in ("id", "kind"):
        need(meta[key] == record[key], f"artifact {key} mismatch")
    need(meta["company"] == state["company"] and meta["product"] == state["product"], "cross-company/product artifact")
    need(meta["author"] == record.get("agent", state["team"][record["role"]]), "artifact author differs from assigned owner")
    need(meta["status"] in ("pending", "confirmed", "not_applicable"), "invalid artifact status")
    if meta["kind"] in ("fact_check", "review", "style_check", "publish") and not allow_pending:
        need(meta["status"] == "confirmed", "review gates cannot be skipped")
    contract = policy["kinds"][meta["kind"]]
    need(record["path"].startswith(contract["prefix"]) and path.suffix == ".md", "artifact category/path mismatch")
    need(isinstance(meta["sources"], list) and all(s in source_ids for s in meta["sources"]), "unknown evidence source ID")
    if meta["status"] == "pending":
        need(allow_pending, "pending artifact blocks phase completion")
    elif meta["status"] == "not_applicable":
        need(meta.get("reason"), "not_applicable needs reason")
    else:
        need(meta["sources"], "confirmed artifact needs sources")
        headings = re.findall(r"^## (.+)$", body, re.M)
        need(set(contract["headings"]) <= set(headings), "missing required Markdown headings")
        for heading in contract["headings"]:
            match = re.search(r"^## " + re.escape(heading) + r"\r?\n(.*?)(?=^## |\Z)", body, re.M | re.S)
            section = match[1].strip()
            need(section and section not in ("작성 필요", "미확정", "TODO", "TBD"), f"unwritten section: {heading}")
        if meta["kind"] in ("fact_check", "review", "style_check"):
            need(meta.get("verdict") == "pass", "review must explicitly pass")
        if meta['kind'] in ('style_check', 'publish') and not allow_pending:
            from creator import digest
            outputs = meta.get('outputs', [])
            need(outputs, 'reviewed output files required')
            need(set(state.get('requested_formats', ['pdf'])) <= {o.get('format') for o in outputs}, 'requested output formats missing')
            for output in outputs:
                file = scoped(run, output['path'])
                need(output['format'] in ('pdf', 'docx', 'html', 'xlsx') and file.suffix == '.' + output['format'], 'output format mismatch')
                need(file.is_file() and digest(file) == output.get('sha256'), 'reviewed output missing or changed')
                need(output.get('review_status') == 'passed' and output.get('reviewer') and output.get('review_notes'), 'output needs explicit review evidence')
    for target in re.findall(r"(?<!!)\[[^\]]*\]\(([^)]+)\)", body):
        if target.startswith(("http://", "https://", "#")):
            continue
        local = target.split("#", 1)[0]
        need(not Path(local).is_absolute(), "Markdown internal links must be relative")
        need(scoped(run, str(path.parent.relative_to(run) / local)).exists(), "broken Markdown link")
    for alt, target in re.findall(r"!\[([^\]]*)\]\(([^)]+)\)", body):
        need(alt.strip() and not target.startswith(("http:", "https:")), "images require local evidence and alt text")
        image = scoped(run, str(path.parent.relative_to(run) / target))
        need(image.is_file(), "missing Markdown image")
        registry = read(run / "sources/evidence-index.json")
        need(any(scoped(run, s["path"]) == image and s["id"] in meta["sources"] for s in registry), "image must be registered and cited as evidence")
    return meta, body


def blocks(body, base=None, run=None):
    """Conservative Markdown-to-layout adapter. Never executes HTML or code."""
    lines = body.splitlines()
    out, pending = [], []
    def flush():
        if pending:
            out.append({"type": "paragraph", "text": "\n".join(pending)})
            pending.clear()
    i = 0
    while i < len(lines):
        line = lines[i]
        fence = re.fullmatch(r' {0,3}(`{3,}|~{3,})([^\n]*)', line)
        if fence:
            flush()
            marker = fence[1]
            code = []
            i += 1
            while i < len(lines) and not re.fullmatch(r' {0,3}' + re.escape(marker[0]) + '{' + str(len(marker)) + r',}\s*', lines[i]):
                code.append(lines[i]); i += 1
            need(i < len(lines), "unclosed Markdown fence")
            out.append({"type": "code", "text": "\n".join(code) or " "})
        elif line.startswith("|") and i + 1 < len(lines) and re.fullmatch(r"[| :\-]+", lines[i + 1]):
            flush()
            cells = lambda value: [c.strip().replace(r"\|", "|") for c in re.split(r"(?<!\\)\|", value.strip().strip("|"))]
            headers, rows = cells(line), []
            i += 2
            while i < len(lines) and lines[i].startswith("|"):
                rows.append(cells(lines[i])); i += 1
            out.append({"type": "table", "headers": headers, "rows": rows})
            continue
        elif line.startswith("> [!"):
            flush()
            label = re.match(r"> \[!(NOTE|WARNING|EXAMPLE)\]\s*(.*)", line)
            need(label, "unsupported note type")
            note = [label[2]] if label[2] else []
            i += 1
            while i < len(lines) and lines[i].startswith("> "):
                note.append(lines[i][2:]); i += 1
            out.append({"type": "note", "role": {"NOTE": "info", "WARNING": "warning", "EXAMPLE": "example"}[label[1]], "text": "\n".join(note)})
            continue
        elif line.startswith("!["):
            flush()
            match = re.fullmatch(r"!\[([^\]]+)\]\(([^)]+)\)", line)
            need(match and base and run, "image must be a standalone local Markdown image")
            file = scoped(run, str(base.relative_to(run) / match[2]))
            out.append({"type": "image", "path": str(file), "alt": match[1]})
        elif re.match(r"#{2,4} ", line):
            flush()
            level = len(line) - len(line.lstrip("#"))
            out.append({"type": "heading", "level": level, "text": line[level+1:]})
        elif line.startswith(("#"*5 + " ", "#"*6 + " ")):
            raise ValueError("heading levels 5 and 6 are not supported")
        elif line.startswith("# "):
            flush()
        elif not line.strip():
            flush()
        else:
            pending.append(line)
        i += 1
    flush()
    return out
