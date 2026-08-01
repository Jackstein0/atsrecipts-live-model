from __future__ import annotations

import os
from pathlib import Path


CHECKS = [
    ("Odds API key in .env", lambda root: _has_api_key(root / ".env")),
    ("historical training data", lambda root: (root / "data/processed/historical_games.csv").exists()),
    ("team metrics", lambda root: _has_rows(root / "data/source/team_metrics.csv")),
    ("starter metrics", lambda root: _has_rows(root / "data/source/starter_metrics.csv")),
    ("bullpen metrics", lambda root: _has_rows(root / "data/source/bullpen_metrics.csv")),
    ("park metrics", lambda root: _has_rows(root / "data/source/park_metrics.csv")),
]


def print_status(root_path: str = ".") -> bool:
    root = Path(root_path)
    print("MLB Run Totals Tool Status")
    print("==========================")
    all_ready = True
    for label, check in CHECKS:
        ready = check(root)
        all_ready = all_ready and ready
        print(f"{'OK  ' if ready else 'MISS'} {label}")
    print()
    if all_ready:
        print("Everything required for a real run appears to be in place.")
    else:
        print("Some setup is still missing. Run Setup.command, then fill the missing files.")
    return all_ready


def _has_api_key(path: Path) -> bool:
    paste_file = path.parent / "PASTE_API_KEY_HERE.txt"
    if _has_api_key_in_paste_file(paste_file):
        return True
    if not path.exists():
        return False
    for line in path.read_text().splitlines():
        if line.startswith("THE_ODDS_API_KEY="):
            value = line.split("=", 1)[1].strip().strip('"').strip("'")
            return value not in ("", "put_your_key_here")
    return bool(os.environ.get("THE_ODDS_API_KEY"))


def _has_api_key_in_paste_file(path: Path) -> bool:
    if not path.exists():
        return False
    for line in path.read_text().splitlines():
        if line.startswith("THE_ODDS_API_KEY="):
            value = line.split("=", 1)[1].strip().strip('"').strip("'")
            return value not in ("", "put_your_key_here")
    return False


def _has_rows(path: Path) -> bool:
    if not path.exists():
        return False
    lines = [line for line in path.read_text().splitlines() if line.strip()]
    return len(lines) > 1
