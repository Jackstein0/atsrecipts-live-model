from __future__ import annotations

import os
import subprocess
import threading
import time
from pathlib import Path

from flask import Flask, Response, jsonify, request


ROOT_DIR = Path(__file__).resolve().parent
REPORT_PATH = ROOT_DIR / "data" / "processed" / "model_report.html"
UPDATE_SCRIPT = ROOT_DIR / "scripts" / "update_all_model_boards.sh"

MAX_AGE_SECONDS = int(os.environ.get("BOARD_MAX_AGE_SECONDS", "900"))
REFRESH_ON_VIEW = os.environ.get("REFRESH_ON_VIEW", "1") != "0"
CRON_SECRET = os.environ.get("CRON_SECRET", "")

app = Flask(__name__)
_update_lock = threading.Lock()
_last_error = ""


def _report_age_seconds() -> float | None:
    if not REPORT_PATH.exists():
        return None
    return max(0.0, time.time() - REPORT_PATH.stat().st_mtime)


def _is_stale() -> bool:
    age = _report_age_seconds()
    return age is None or age > MAX_AGE_SECONDS


def _run_update() -> None:
    global _last_error
    if not UPDATE_SCRIPT.exists():
        raise RuntimeError(f"Missing updater: {UPDATE_SCRIPT}")

    env = os.environ.copy()
    env["PUBLIC_REPORT"] = str(REPORT_PATH)

    result = subprocess.run(
        ["bash", str(UPDATE_SCRIPT)],
        cwd=str(ROOT_DIR),
        env=env,
        text=True,
        capture_output=True,
        timeout=int(os.environ.get("BOARD_UPDATE_TIMEOUT_SECONDS", "240")),
    )
    if result.returncode != 0:
        _last_error = (result.stderr or result.stdout or "Unknown update failure").strip()
        raise RuntimeError(_last_error)
    _last_error = ""


def _ensure_fresh(force: bool = False) -> bool:
    if not force and not _is_stale():
        return False
    if not _update_lock.acquire(blocking=False):
        return False
    try:
        if force or _is_stale():
            _run_update()
            return True
        return False
    finally:
        _update_lock.release()


def _authorized() -> bool:
    if not CRON_SECRET:
        return True
    header = request.headers.get("Authorization", "")
    return header == f"Bearer {CRON_SECRET}" or request.args.get("secret") == CRON_SECRET


@app.get("/")
def index() -> Response:
    try:
        if REFRESH_ON_VIEW:
            _ensure_fresh()
    except Exception:
        if not REPORT_PATH.exists():
            raise

    if not REPORT_PATH.exists():
        return Response("No model report has been generated yet.", status=503, mimetype="text/plain")

    return Response(REPORT_PATH.read_text(), mimetype="text/html")


@app.get("/refresh")
def refresh() -> Response:
    if not _authorized():
        return Response("Unauthorized", status=401, mimetype="text/plain")
    _ensure_fresh(force=True)
    return jsonify({"ok": True, "updated": True, "report_age_seconds": _report_age_seconds()})


@app.get("/healthz")
def healthz() -> Response:
    return jsonify(
        {
            "ok": True,
            "report_exists": REPORT_PATH.exists(),
            "report_age_seconds": _report_age_seconds(),
            "stale": _is_stale(),
            "last_error": _last_error,
        }
    )


if __name__ == "__main__":
    port = int(os.environ.get("PORT", "10000"))
    app.run(host="0.0.0.0", port=port)
