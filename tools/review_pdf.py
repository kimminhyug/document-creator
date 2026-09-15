"""Rasterize one generated PDF for human inspection; never auto-approve layout."""
import argparse
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from creator import digest, read_json, write_json


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("run_dir", type=Path)
    parser.add_argument("--runtime", type=Path, default=ROOT / ".local/runtime.json")
    args = parser.parse_args()
    run = args.run_dir.resolve()
    pdf = run / "document.pdf"
    manifest = read_json(run / "manifest.json")
    if manifest["outputs"].get("document.pdf") != digest(pdf):
        raise ValueError("PDF changed since build; rebuild before review")
    runtime = read_json(args.runtime)
    target = run / "pdf-review"
    target.mkdir(exist_ok=True)
    subprocess.run([runtime["pdftoppm"], "-scale-to", "1500", "-png", str(pdf), str(target / "page")], check=True, timeout=120)
    pages = sorted(target.glob("page-*.png"))
    if not pages:
        raise RuntimeError("No rendered pages")
    write_json(target / "review.json", {"pdf_sha256": digest(pdf), "pages": [p.name for p in pages], "status": "needs_visual_review", "checks": ["한글 누락", "표 잘림·겹침", "제목 고립", "머릿글·바닥글", "마지막 페이지"]})
    print(target)


if __name__ == "__main__":
    main()
