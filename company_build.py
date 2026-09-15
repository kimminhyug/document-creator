"""Company-approved build entry: theme is resolved from company, never AI content."""
from config_paths import entity_dir
import argparse
from pathlib import Path
from collector.config import ROOT, IDENTIFIER, need, read, scoped
from creator import build


def settings(product, document_type):
    need(IDENTIFIER.fullmatch(product), "invalid product ID")
    folder = entity_dir(ROOT, "products", product)
    meta = read(folder / "product.json")
    need(meta["id"] == product and IDENTIFIER.fullmatch(meta["company"]), "invalid product/company")
    company_dir = entity_dir(ROOT, "companies", meta["company"])
    company = read(company_dir / "company.json")
    need(company["id"] == meta["company"] and document_type in company["templates"], "document template not approved")
    theme = scoped(company_dir, company["theme"])
    project = scoped(folder, "document-project.json")
    need(read(project)["organization"] == company["organization"], "project organization differs from company standard")
    return company, theme, project, ROOT / "templates" / (document_type + ".json")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--product", required=True)
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--formats", nargs="+", choices=["pdf", "docx", "html", "xlsx"], default=["pdf"])
    args = parser.parse_args()
    content = read(args.input)
    if "theme" in content or "style" in content:
        raise ValueError("AI document must not override company styles")
    company, theme, project, template = settings(args.product, content["type"])
    print(build(args.input, template, project, theme, ROOT / ".local/runtime.json", ROOT / "output/documents" / company["id"] / args.product, args.formats))


if __name__ == "__main__":
    main()
