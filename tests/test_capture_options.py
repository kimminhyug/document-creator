import asyncio
import copy
import json
import tempfile
import threading
import time
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from unittest.mock import patch

from collect import collect
from collector.config import ROOT, capture_profile, load, prepare_capture, prepare_login, read


class CaptureOptionTests(unittest.TestCase):
    def setUp(self):
        self.profile = capture_profile(read(ROOT / "profiles/capture/desktop.json"))
        self.base = "http://127.0.0.1:8765"

    def test_legacy_defaults_and_profile_validation(self):
        self.assertEqual(self.profile["color_scheme"], "light")
        legacy = {k: v for k, v in self.profile.items() if k not in ("color_scheme", "navigation_timeout_ms", "api_timeout_ms")}
        resolved = capture_profile(legacy)
        self.assertEqual(resolved["api_timeout_ms"], legacy["timeout_ms"])
        for field, value in (("color_scheme", "auto"), ("locale", "../../secret"), ("api_timeout_ms", -1)):
            bad = {**self.profile, field: value}
            with self.assertRaises(ValueError):
                capture_profile(bad)
        bad = {**self.profile, "viewport": {"width": True, "height": 800}}
        with self.assertRaises(ValueError):
            capture_profile(bad)

    def test_paths_response_origins_and_safe_output(self):
        page = {"id": "summary", "output_subdir": "manual/dashboard", "filename": "overview", "wait_for_responses": [{"path": "/api/data"}]}
        prepare_capture(page, self.profile, self.base, [self.base])
        self.assertEqual(page["output_prefix"], "manual/dashboard/light/ko-KR/1280x800/overview")
        self.assertEqual(page["wait_for_responses"][0]["url"], self.base + "/api/data")
        for bad in ({"output_subdir": "../escape"}, {"filename": "../escape"}, {"wait_for_responses": [{"path": "https://other.test/data"}]}):
            with self.assertRaises(ValueError):
                prepare_capture({"id": "summary", **bad}, self.profile, self.base, [self.base])

    def test_login_only_accepts_scoped_env_references(self):
        login = login_config()
        prepare_login({"login": login}, "DOC__DEMO__LOCAL", self.base, [self.base])
        for env in ({"login": {**login, "password": "must-not-persist"}}, {"login": {**login, "password_env": "OTHER_PASSWORD"}}, {"login": login, "auth_state_env": "DOC__DEMO__LOCAL_AUTH_STATE"}):
            with self.assertRaises(ValueError):
                prepare_login(env, "DOC__DEMO__LOCAL", self.base, [self.base])


def login_config():
    return {"path": "/login", "username_env": "DOC__DEMO__LOCAL_LOGIN_USERNAME", "password_env": "DOC__DEMO__LOCAL_LOGIN_PASSWORD", "username_selector": "#username", "password_selector": "#password", "submit_selector": "#submit", "success_selector": "#authenticated"}


class FixtureHandler(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def do_GET(self):
        if self.path == "/api/data":
            time.sleep(0.25)
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b'{"ready":true}')
            return
        if self.path == "/login":
            body = '''<input id="username"><input id="password" type="password"><button id="submit" onclick="document.cookie='session=yes;path=/';document.body.innerHTML='<div id=authenticated>ok</div>'">Sign in</button>'''
        elif self.path == "/dashboard" and "session=yes" in self.headers.get("Cookie", ""):
            body = '''<style>html,body{margin:0;background:white}@media(prefers-color-scheme:dark){html,body{background:rgb(10,20,30)}}</style><div id="ready">waiting</div><script>fetch('/api/data').then(r=>r.json()).then(()=>{document.querySelector('#ready').textContent=navigator.language;document.body.dataset.loaded='yes';document.body.dataset.locale=navigator.language})</script>'''
        else:
            self.send_response(403)
            self.end_headers()
            return
        self.send_response(200)
        self.send_header("Content-Type", "text/html")
        self.end_headers()
        self.wfile.write(body.encode())


class CaptureOptionIntegrationTests(unittest.TestCase):
    def test_login_dark_locale_viewport_response_wait_and_secret_free_outputs(self):
        runtime_path = ROOT / ".local/runtime.json"
        if not runtime_path.exists() or "chromium" not in read(runtime_path):
            self.skipTest("Playwright runtime required")
        server = ThreadingHTTPServer(("127.0.0.1", 0), FixtureHandler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            config = load("demo", "local")
            base = f"http://127.0.0.1:{server.server_port}"
            config["allowed_origins"] = [base]
            profile = config["profile"]
            profile.update(color_scheme="dark", locale="en-US", viewport={"width": 640, "height": 480}, navigation_timeout_ms=3000, api_timeout_ms=1500)
            config["login"] = prepare_login({"login": login_config()}, "DOC__DEMO__LOCAL", base, [base])
            page = {"id": "dashboard", "url": base + "/dashboard", "mode": "viewport", "ready_selector": "body[data-loaded=yes][data-locale=en-US] #ready", "output_subdir": "manual", "filename": "summary", "wait_for_responses": [{"path": "/api/data"}]}
            prepare_capture(page, profile, base, [base])
            missing = {"id": "missing-api", "url": base + "/dashboard", "mode": "viewport", "ready_selector": "#ready", "wait_for_responses": [{"path": "/api/never"}]}
            prepare_capture(missing, profile, base, [base])
            config["pages"] = [page, missing]
            secrets = {"DOC__DEMO__LOCAL_LOGIN_USERNAME": "fixture-account-924", "DOC__DEMO__LOCAL_LOGIN_PASSWORD": "fixture-secret-924"}
            with tempfile.TemporaryDirectory() as temp, patch.dict("os.environ", secrets):
                run, manifest = asyncio.run(collect(config, read(runtime_path), temp))
                results = {item["id"]: item for item in manifest["captures"]}
                self.assertEqual(results["dashboard"]["status"], "passed", manifest)
                self.assertEqual(results["missing-api"]["error"], "Timeout")
                path = results["dashboard"]["files"][0]["path"]
                self.assertEqual(path, "screenshots/manual/dark/en-US/640x480/summary-001.png")
                from PIL import Image
                with Image.open(run / path) as image:
                    self.assertEqual(image.size, (640, 480))
                    self.assertEqual(image.convert("RGB").getpixel((400, 300)), (10, 20, 30))
                for file in run.rglob("*"):
                    if file.is_file():
                        for secret in secrets.values():
                            self.assertNotIn(secret.encode(), file.read_bytes())
        finally:
            server.shutdown()
            server.server_close()
            thread.join()


if __name__ == "__main__":
    unittest.main()


