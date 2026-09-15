from config_paths import entity_dir
import copy
import json
import re
from pathlib import Path
from urllib.parse import urljoin, urlsplit

ROOT = Path(__file__).resolve().parents[1]
IDENTIFIER = re.compile(r"(?=.{1,64}\Z)[a-z][a-z0-9]*(?:-[a-z0-9]+)*\Z")


def need(ok, message):
    if not ok:
        raise ValueError(message)


def read(path):
    return json.loads(Path(path).read_text(encoding="utf-8-sig"))


def scoped(root, relative):
    path = (root / relative).resolve()
    need(path.is_relative_to(root.resolve()), "path escapes product directory")
    return path


def origin(url):
    parsed = urlsplit(url)
    need(parsed.scheme in ("http", "https") and parsed.hostname and not parsed.username and not parsed.password, "HTTP(S) URL without credentials required")
    return f"{parsed.scheme}://{parsed.netloc}"


def capture_profile(profile):
    """Resolve backwards-compatible defaults before crossing the worker boundary."""
    profile = copy.deepcopy(profile)
    need(profile.get("color_scheme", "light") in ("light", "dark"), "color_scheme must be light/dark")
    profile.setdefault("color_scheme", "light")
    for key in ("navigation_timeout_ms", "api_timeout_ms"):
        profile.setdefault(key, profile["timeout_ms"])
        need(type(profile[key]) is int and 100 <= profile[key] <= 120000, f"invalid {key}")
    need(isinstance(profile.get("locale"), str) and re.fullmatch(r"[A-Za-z]{2,8}(?:-[A-Za-z0-9]{1,8})*", profile["locale"]), "invalid locale")
    need(isinstance(profile.get("timezone"), str) and profile["timezone"].strip(), "timezone required")
    viewport = profile["viewport"]
    need(all(type(viewport.get(k)) is int for k in ("width", "height")), "viewport dimensions must be integers")
    return profile


def relative_capture_path(value):
    need(isinstance(value, str) and value and all(IDENTIFIER.fullmatch(part) for part in value.split("/")), "capture subfolder must use safe kebab-case components")
    return value


def prepare_capture(page, profile, base, allowed):
    waits = page.get("wait_for_responses", [])
    need(isinstance(waits, list) and len(waits) <= 20, "wait_for_responses must have at most 20 entries")
    for wait in waits:
        need(isinstance(wait, dict) and set(wait) <= {"path", "method", "status"}, "invalid response wait")
        need(isinstance(wait.get("path"), str) and wait["path"], "response path required")
        url = urljoin(base, wait["path"])
        need(origin(url) in allowed, "response wait origin not allowed")
        need(not urlsplit(url).fragment, "response URL cannot contain fragment")
        wait["url"] = url
        wait.setdefault("method", "GET")
        wait.setdefault("status", 200)
        need(wait["method"] in ("GET", "POST", "PUT", "PATCH", "DELETE", "HEAD", "OPTIONS"), "invalid response method")
        need(type(wait["status"]) is int and 100 <= wait["status"] <= 599, "invalid response status")
    folder = page.get("output_subdir")
    if folder is not None:
        relative_capture_path(folder)
    filename = page.get("filename", page["id"])
    need(isinstance(filename, str) and IDENTIFIER.fullmatch(filename), "filename must be a kebab-case stem without extension")
    viewport = profile["viewport"]
    dimensions = f"{viewport['width']}x{viewport['height']}"
    page["output_prefix"] = "/".join(filter(None, (folder, profile["color_scheme"], profile["locale"], dimensions, filename)))


def prepare_login(env, prefix, base, allowed):
    login = copy.deepcopy(env.get("login"))
    if login is None:
        return None
    keys = {"path", "username_env", "password_env", "username_selector", "password_selector", "submit_selector", "success_selector"}
    need(isinstance(login, dict) and set(login) == keys, "login requires only selectors, path and credential environment references")
    need(not env.get("auth_state_env"), "choose login or auth_state_env, not both")
    need(login["username_env"] == prefix + "_LOGIN_USERNAME" and login["password_env"] == prefix + "_LOGIN_PASSWORD", "login credentials must use product/environment LOGIN scope")
    need(all(isinstance(login[k], str) and login[k].strip() for k in keys), "login values must be nonempty strings")
    login["url"] = urljoin(base, login["path"])
    need(origin(login["url"]) in allowed, "login origin not allowed")
    return login


def load(product, environment, root=ROOT):
    need(IDENTIFIER.fullmatch(product) and IDENTIFIER.fullmatch(environment), "invalid product/environment ID")
    folder = entity_dir(root, "products", product)
    env = read(folder / "environments" / (environment + ".json"))
    meta = read(folder / "product.json")
    need(meta["id"] == product and env["product"] == product and env["environment"] == environment, "product/environment mismatch")
    need(IDENTIFIER.fullmatch(meta["company"]), "company ID required")
    company = read(entity_dir(root, "companies", meta["company"]) / "company.json")
    need(company["id"] == meta["company"], "company mismatch")
    capture = read(scoped(folder, env["capture"]))
    profile_id = env["capture_profile"]
    need(IDENTIFIER.fullmatch(profile_id), "invalid capture profile")
    need(profile_id in company["capture_profiles"], "capture profile not approved by company")
    profile = capture_profile(read(root / "profiles/capture" / (profile_id + ".json")))
    need(1 <= profile["workers"] <= 8, "workers must be 1..8")
    need(1000 <= profile["timeout_ms"] <= 120000, "timeout must be 1000..120000")
    need(1 <= profile["max_segments"] <= 100, "max_segments must be 1..100")
    viewport = profile["viewport"]
    need(320 <= viewport["width"] <= 3840 and 240 <= viewport["height"] <= 2160, "viewport outside bounds")
    need(0 <= profile["overlap_px"] < viewport["height"], "invalid segment overlap")
    base = env["base_url"]
    env_prefix = f"DOC__{product.upper().replace('-', '_')}__{environment.upper().replace('-', '_')}"
    need(env.get("auth_state_env") in (None, env_prefix + "_AUTH_STATE"), "auth state must be product/environment scoped")
    allowed = [origin(u) for u in env["allowed_origins"]]
    need(origin(base) in allowed, "base origin not allowed")
    login = prepare_login(env, env_prefix, base, allowed)
    tasks = copy.deepcopy(capture["pages"])
    need(isinstance(tasks, list) and 0 < len(tasks) <= 500, "pages must contain 1..500 entries")
    ids, output_paths = set(), set()
    for page in tasks:
        need(IDENTIFIER.fullmatch(page["id"]) and page["id"] not in ids, "duplicate/invalid page ID")
        ids.add(page["id"])
        page["url"] = urljoin(base, page["path"])
        need(origin(page["url"]) in allowed, "page origin not allowed")
        need(page["mode"] in ("viewport", "segments", "element"), "unsupported screenshot mode")
        need(isinstance(page.get("ready_selector"), str) and page["ready_selector"], "ready_selector required")
        need(isinstance(page.get("masks", []), list) and all(isinstance(s, str) and s for s in page.get("masks", [])), "masks must be selectors")
        if page["mode"] == "element":
            need(isinstance(page.get("selector"), str) and page["selector"], "element selector required")
        prepare_capture(page, profile, base, allowed)
        need(page["output_prefix"].casefold() not in output_paths, "duplicate capture output path")
        output_paths.add(page["output_prefix"].casefold())
    db = None
    if env.get("database"):
        db = read(scoped(folder, env["database"]))
        need(db["driver"] == "postgresql", "only PostgreSQL is supported")
        need(db["connection_env_prefix"] == env_prefix, "database env prefix must be product/environment scoped")
        need(1 <= db["max_rows"] <= 10000, "max_rows must be 1..10000")
        need(100 <= db["timeout_ms"] <= 60000, "DB timeout must be 100..60000")
        need(1 <= db["max_cell_chars"] <= 4096, "max_cell_chars must be 1..4096")
        from collector.postgres import compile_query
        qids = set()
        for query in db["queries"]:
            need(IDENTIFIER.fullmatch(query["id"]) and query["id"] not in qids, "duplicate/invalid query ID")
            qids.add(query["id"])
            compile_query(db, query)
    return {"company": company["id"], "product": product, "environment": environment, "profile": profile, "pages": tasks, "database": db, "allowed_origins": allowed, "auth_state_env": env.get("auth_state_env"), "login": login, "inputs": {"company": company, "environment": env, "capture": capture, "profile": profile, "database": db}}
