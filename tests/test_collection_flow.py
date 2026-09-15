import asyncio
import copy
import json
import tempfile
import threading
import unittest
from http.server import ThreadingHTTPServer
from pathlib import Path
from unittest.mock import patch

from collector.config import ROOT, load, read
from collector.postgres import compile_query, script
from collect import collect
import flow
from md_contract import parse, write_artifact
from md_contract import blocks
from examples.demo.tools.demo_capture_server import Handler


class QueryPolicyTests(unittest.TestCase):
    def setUp(self):
        self.config = read(ROOT / "examples/demo/products/demo/database/readonly.json")
        self.query = copy.deepcopy(self.config["queries"][0])

    def test_raw_sql_and_unapproved_columns_are_denied(self):
        self.query["sql"] = "DELETE FROM equipment"
        with self.assertRaisesRegex(ValueError, "raw SQL"):
            compile_query(self.config, self.query)
        self.query.pop("sql")
        self.query["columns"] = ["password"]
        with self.assertRaisesRegex(ValueError, "approved"):
            compile_query(self.config, self.query)

    def test_injection_is_literal_not_sql(self):
        self.query["filters"] = [{"column": "equipment_id", "op": "eq", "value": "x'; DROP TABLE equipment; --"}]
        sql, _ = compile_query(self.config, self.query)
        self.assertIn("'x''; DROP TABLE equipment; --'", sql)
        self.assertTrue(sql.endswith("LIMIT 101"))
        self.query["filters"][0]["value"] = "\\q\n"
        with self.assertRaises(ValueError):
            compile_query(self.config, self.query)

    def test_script_readonly_privilege_gate_and_rollback(self):
        sql = script(self.config, self.query)
        self.assertIn("BEGIN TRANSACTION READ ONLY", sql)
        self.assertIn("NOT rolsuper", sql)
        self.assertIn("has_any_column_privilege", sql)
        self.assertIn("statement_timeout", sql)
        self.assertTrue(sql.rstrip().endswith("ROLLBACK;"))

    def test_product_names_cannot_alias_secret_prefixes(self):
        from collector.config import IDENTIFIER
        self.assertTrue(IDENTIFIER.fullmatch("foo-bar"))
        self.assertFalse(IDENTIFIER.fullmatch("foo_bar"))
        self.assertFalse(IDENTIFIER.fullmatch("foo--bar"))
        self.assertNotEqual("DOC__FOO_BAR__DEV", "DOC__FOO__BAR_DEV")


class WorkflowTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.run = flow.initialize("demo", base=Path(self.temp.name))

    def tearDown(self):
        self.temp.cleanup()

    def confirm_scope(self):
        source = Path(self.temp.name) / "request.md"
        source.write_text("이 제품의 문서 작성 범위를 조사한다.", encoding="utf-8")
        flow.register_source(self.run, "request-001", source)
        state = read(self.run / "state.json")
        record = state["artifacts"][0]
        path = self.run / record["path"]
        meta, body = parse(path)
        meta.update(status="confirmed", sources=["request-001"])
        write_artifact(path, meta, body.replace("작성 필요", "등록한 요청을 기준으로 범위를 정한다."))
        return path

    def test_classified_files_and_ownership(self):
        state = read(self.run / "state.json")
        paths = [a["path"] for a in state["artifacts"]]
        self.assertEqual(len(paths), len(set(paths)))
        self.assertTrue(any(p.startswith("research/data/tables/") for p in paths))
        self.assertTrue(any(p.startswith("documents/table_spec/sections/") for p in paths))
        self.assertNotEqual(state["team"]["writer"], state["team"]["reviewer"])
        self.assertTrue(list(flow.tasks(self.run).glob("*.md")))

    def test_pending_gate_and_wrong_actor_fail(self):
        with self.assertRaisesRegex(ValueError, "pending"):
            flow.advance(self.run, "document-lead")
        self.confirm_scope()
        with self.assertRaisesRegex(ValueError, "actor"):
            flow.advance(self.run, "document-writer")

    def test_pass_then_changes_require_rework(self):
        path = self.confirm_scope()
        flow.advance(self.run, "document-lead")
        self.assertEqual(read(self.run / "state.json")["phase"], 1)
        path.write_text(path.read_text(encoding="utf-8") + "\n수정", encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "changed"):
            flow.tasks(self.run)
        flow.rework(self.run, "intake", "범위 수정", "document-lead")
        self.assertFalse(read(self.run / "state.json")["passed"])

    def test_cross_product_artifact_is_rejected(self):
        path = self.confirm_scope()
        meta, body = parse(path)
        meta["product"] = "another-product"
        write_artifact(path, meta, body)
        with self.assertRaisesRegex(ValueError, "cross-company"):
            flow.advance(self.run, "document-lead")

    def test_markdown_keeps_headings_and_escaped_table_pipes(self):
        result = blocks("## Heading\n\n| A | B |\n| --- | --- |\n| a\\|b | x |\n")
        self.assertEqual(result[0], {"type": "heading", "level": 2, "text": "Heading"})
        self.assertEqual(result[1]["rows"], [["a|b", "x"]])


class CaptureIntegrationTests(unittest.TestCase):
    def test_parallel_segments_masks_and_failed_page(self):
        runtime_path = ROOT / ".local/runtime.json"
        if not runtime_path.exists() or "chromium" not in read(runtime_path):
            self.skipTest("Playwright runtime required")
        server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            config = load("demo", "local")
            base = f"http://127.0.0.1:{server.server_port}"
            config["allowed_origins"] = [base]
            for page in config["pages"]:
                page["url"] = base + page["path"]
            config["pages"].append({"id": "missing", "url": base + "/missing", "mode": "viewport", "ready_selector": "#ready"})
            with tempfile.TemporaryDirectory() as temp:
                run, manifest = asyncio.run(collect(config, read(runtime_path), temp))
                self.assertEqual(manifest["status"], "partial_failure")
                passed = [r for r in manifest["captures"] if r["status"] == "passed"]
                self.assertEqual(len(passed), 3)
                self.assertEqual(len({r["pid"] for r in passed}), 2)
                summary = next(r for r in passed if r["id"] == "summary")
                self.assertGreater(len(summary["files"]), 1)
                from PIL import Image
                image = Image.open(run / summary["files"][0]["path"]).convert("RGB")
                self.assertEqual(image.size, (1280, 800))
                self.assertEqual(image.getpixel((60, 125)), (34, 34, 34))
        finally:
            server.shutdown()
            server.server_close()
            thread.join()


if __name__ == "__main__":
    unittest.main()
