import copy
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import creator


class ValidationTests(unittest.TestCase):
    def setUp(self):
        self.data = creator.read_json(creator.ROOT / "examples/demo/content/table-spec.json")
        self.contract = creator.read_json(creator.ROOT / "templates/table_spec.json")
        self.project = creator.read_json(creator.ROOT / "examples/demo/content/project.json")
        self.theme = creator.read_json(creator.ROOT / "themes/blue-office.json")

    def validate(self, release=False):
        return creator.validate(self.data, self.contract, self.project, self.theme, release)

    def test_example_is_labeled_and_cannot_release(self):
        self.assertTrue(self.validate())
        with self.assertRaisesRegex(ValueError, "release blocked"):
            self.validate(True)

    def test_missing_section_fails(self):
        self.data["sections"].pop()
        with self.assertRaisesRegex(ValueError, "missing required"):
            self.validate()

    def test_broken_reference_fails(self):
        self.data["sections"][0]["refs"] = ["no-such-section"]
        with self.assertRaisesRegex(ValueError, "unknown section"):
            self.validate()

    def test_confirmed_content_needs_traceable_source(self):
        self.data["sections"][0]["sources"] = []
        with self.assertRaisesRegex(ValueError, "needs source"):
            self.validate()

    def test_bad_table_row_fails(self):
        self.data["sections"][1]["blocks"][0]["rows"][0].pop()
        with self.assertRaisesRegex(ValueError, "table cells"):
            self.validate()

    def test_duplicate_section_fails(self):
        self.data["sections"].append(copy.deepcopy(self.data["sections"][0]))
        with self.assertRaisesRegex(ValueError, "duplicate section"):
            self.validate()

    def test_pending_content_not_invented(self):
        self.data["example"] = False
        s = self.data["sections"][0]
        s.update(status="pending", reason="입력 미확정", owner="담당자", blocks=[], sources=[])
        self.assertIn("미확정", self.validate()[0])
        with self.assertRaisesRegex(ValueError, "release blocked"):
            self.validate(True)

    def test_wrong_theme_color_fails(self):
        self.theme["notes"]["info"]["marker"] = "blue-ish"
        with self.assertRaisesRegex(ValueError, "invalid note color"):
            self.validate()

    def test_all_starter_templates_are_valid_drafts(self):
        for path in (creator.ROOT / "examples/demo/content").glob("*-starter.json"):
            data = creator.read_json(path)
            contract = creator.read_json(creator.ROOT / "templates" / (data["type"] + ".json"))
            self.assertTrue(creator.validate(data, contract, self.project, self.theme))

    def test_builds_never_clobber_and_failures_do_not_publish(self):
        paths = [creator.ROOT / name for name in ("examples/demo/content/table-spec.json", "templates/table_spec.json", "examples/demo/content/project.json", "themes/blue-office.json")]
        with tempfile.TemporaryDirectory() as temp:
            out = Path(temp)
            def writer(path, *_):
                Path(path).write_bytes(b"fixture")
            with patch.object(creator, "render_docx", side_effect=writer):
                first = creator.build(*paths, None, out, ["docx"])
                second = creator.build(*paths, None, out, ["docx"])
            self.assertNotEqual(first, second)
            report = creator.read_json(first / "manifest.json")
            self.assertEqual(report["visual_review"]["docx"], "not_reviewed")
            with patch.object(creator, "render_docx", side_effect=RuntimeError("conversion failed")):
                with self.assertRaises(RuntimeError):
                    creator.build(*paths, None, out, ["docx"])
            self.assertEqual(len(list(out.iterdir())), 2)

    def test_pdf_long_table_repeats_headers_and_keeps_literal_text(self):
        runtime_path = creator.ROOT / ".local/runtime.json"
        if not runtime_path.exists():
            self.skipTest("configure local PDF fonts for renderer integration test")
        from pypdf import PdfReader
        self.data["sections"][1]["blocks"] = [{"type": "table", "headers": ["COLUMN", "DESCRIPTION"], "rows": [[f"ROW_{i:03d}", "<b>literal</b> & data; " + "Long cell content. " * 5] for i in range(60)]}]
        with tempfile.TemporaryDirectory() as temp:
            pdf = Path(temp) / "long.pdf"
            creator.render_pdf(pdf, self.data, self.project, self.theme, creator.read_json(runtime_path))
            texts = [page.extract_text() for page in PdfReader(pdf).pages]
            full = "\n".join(texts)
            self.assertIn("ROW_059", full)
            self.assertIn("<b>literal</b>", full)
            self.assertGreater(sum("COLUMN" in t for t in texts), 1)
            for i in range(60):
                self.assertEqual(full.count(f"ROW_{i:03d}"), 1)

    def test_docx_contains_real_fields_and_repeating_table_headers(self):
        from zipfile import ZipFile
        from xml.etree import ElementTree as ET
        with tempfile.TemporaryDirectory() as temp:
            file = Path(temp) / "draft.docx"
            creator.render_docx(file, self.data, self.project, self.theme)
            with ZipFile(file) as z:
                xml = ET.fromstring(z.read("word/document.xml"))
                ns = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"}
                self.assertTrue(xml.findall(".//w:tblHeader", ns))
                footer = z.read("word/footer1.xml").decode()
                self.assertIn("NUMPAGES", footer)
                self.assertIn("PAGE", footer)


if __name__ == "__main__":
    unittest.main()
