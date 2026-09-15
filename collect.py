"""Python 3.12 CLI: product-isolated parallel screenshots + PostgreSQL SELECT evidence."""
import argparse
import asyncio
import hashlib
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from collector.config import ROOT, load, read, scoped
from collector.postgres import run_query


def save(path, data):
    Path(path).write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def kill_tree(proc):
    if proc.returncode is not None:
        return
    if os.name == "nt":
        subprocess.run(["taskkill", "/PID", str(proc.pid), "/T", "/F"], capture_output=True, timeout=10)
    else:
        import signal
        os.killpg(proc.pid, signal.SIGKILL)


async def worker(config, pages, runtime, output):
    results = []
    state_var = config.get("auth_state_env")
    auth_state = os.environ.get(state_var) if state_var else None
    if state_var and (not auth_state or not Path(auth_state).is_file()):
        raise ValueError("configured auth state environment variable/file is missing")
    credentials = None
    if config.get("login"):
        credentials = {key: os.environ.get(config["login"][key + "_env"]) for key in ("username", "password")}
        if not all(credentials.values()):
            raise ValueError("configured login credential environment variables are missing")
    # Secrets cross only the process stdin pipe; never command arguments or persisted jobs.
    payload = {"pages": pages, "runtime": {k: runtime[k] for k in ("playwright_module", "chromium")}, "profile": config["profile"], "allowed_origins": config["allowed_origins"], "output": str(output), "auth_state": auth_state, "login": config.get("login"), "credentials": credentials}
    proc = await asyncio.create_subprocess_exec(runtime["node"], str(ROOT / "collector/browser_worker.cjs"), stdin=asyncio.subprocess.PIPE, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.DEVNULL, start_new_session=os.name != "nt")
    try:
        # Bound the whole shard including browser startup and cleanup; kill browser descendants on timeout.
        profile = config["profile"]
        budget = 15 + len(pages) * (3 * profile.get("navigation_timeout_ms", profile["timeout_ms"]) + profile.get("api_timeout_ms", profile["timeout_ms"]) + (profile["max_segments"] + 10) * profile["timeout_ms"]) / 1000
        raw, _ = await asyncio.wait_for(proc.communicate(json.dumps(payload).encode()), timeout=budget)
        for line in raw.decode().splitlines():
            results.append(json.loads(line))
    except (TimeoutError, asyncio.CancelledError):
        kill_tree(proc)
        await proc.wait()
        raise
    finally:
        if proc.returncode is None:
            kill_tree(proc)
            await proc.wait()
    returned = {r["id"] for r in results}
    results.extend({"id": p["id"], "status": "failed", "error": "WorkerExited"} for p in pages if p["id"] not in returned)
    return results


async def collect(config, runtime, base, with_db=False):
    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ") + "-" + uuid4().hex[:8]
    run = Path(base) / config["product"] / config["environment"] / run_id
    run.mkdir(parents=True, exist_ok=False)
    images = run / "screenshots"
    images.mkdir()
    results = []
    manifest = {"company": config["company"], "product": config["product"], "environment": config["environment"], "run_id": run_id, "status": "running", "config_sha256": hashlib.sha256(json.dumps(config["inputs"], sort_keys=True).encode()).hexdigest(), "captures": [], "queries": [], "visual_review": "not_reviewed"}
    save(run / "manifest.json", manifest)
    try:
        count = min(config["profile"]["workers"], len(config["pages"]))
        shards = [config["pages"][n::count] for n in range(count)]
        batches = await asyncio.gather(*(worker(config, shard, runtime, images) for shard in shards), return_exceptions=True)
        for shard, batch in zip(shards, batches):
            if isinstance(batch, BaseException):
                results.extend({"id": p["id"], "status": "failed", "error": type(batch).__name__} for p in shard)
            else:
                results.extend(batch)
        for item in results:
            item["files"] = [{"path": "screenshots/" + f, "sha256": hashlib.sha256(scoped(images, f).read_bytes()).hexdigest()} for f in item.get("files", [])]
        manifest["captures"] = sorted(results, key=lambda r: r["id"])
        if with_db:
            if not config["database"]:
                raise ValueError("this environment has no database configuration")
            dbdir = run / "queries"
            dbdir.mkdir()
            for query in config["database"]["queries"]:
                item = {"id": query["id"], "status": "failed"}
                try:
                    response = await asyncio.to_thread(run_query, config["database"], query, runtime)
                    file = dbdir / (query["id"] + ".json")
                    save(file, response)
                    item.update(status="passed", path="queries/" + file.name, sha256=hashlib.sha256(file.read_bytes()).hexdigest())
                except Exception as exc:
                    item["error"] = type(exc).__name__
                manifest["queries"].append(item)
        all_items = manifest["captures"] + manifest["queries"]
        manifest["status"] = "passed" if all(i["status"] == "passed" for i in all_items) else "partial_failure"
    except BaseException:
        manifest["status"] = "failed"
        raise
    finally:
        manifest["finished"] = datetime.now(timezone.utc).isoformat()
        save(run / "manifest.json", manifest)
    return run, manifest


def main():
    if sys.version_info[:2] != (3, 12):
        raise SystemExit("Python 3.12 is required")
    p = argparse.ArgumentParser()
    p.add_argument("--product", required=True)
    p.add_argument("--environment", required=True)
    p.add_argument("--runtime", type=Path, default=ROOT / ".local/runtime.json")
    p.add_argument("--output", type=Path, default=ROOT / "output/collection")
    p.add_argument("--with-db", action="store_true")
    p.add_argument("--validate-only", action="store_true")
    args = p.parse_args()
    try:
        config = load(args.product, args.environment)
        if args.validate_only:
            print("VALID: " + config["product"] + "/" + config["environment"])
            return 0
        run, manifest = asyncio.run(collect(config, read(args.runtime), args.output, args.with_db))
        print(run)
        return 0 if manifest["status"] == "passed" else 1
    except (ValueError, OSError, KeyError, TypeError) as exc:
        print(f"ERROR: {type(exc).__name__}: configuration/runtime check failed", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
