from __future__ import annotations

from collections import defaultdict
from pathlib import Path

from .features import load_csv, write_csv
from .odds import MLB_TEAM_CODES
from .pricing import american_to_decimal
from .schedule import fetch_mlb_schedule


TRACKER_COLUMNS = [
    "date",
    "away_team",
    "home_team",
    "market_total",
    "commence_time",
    "model_total",
    "bet_side",
    "edge_label",
    "best_ev",
    "odds",
    "actual_total",
    "away_runs",
    "home_runs",
    "result",
    "profit_units",
]


def append_picks(results_path: str, tracker_path: str, min_label: str = "lean") -> tuple[int, int, int]:
    results = load_csv(results_path)
    existing = load_csv(tracker_path) if Path(tracker_path).exists() else []
    by_key = {}
    for row in existing:
        by_key.setdefault(_pick_key(row), row)
    added = 0
    updated = 0
    for row in results:
        if not _include_label(row.get("edge_label", ""), min_label):
            continue
        pick = {
            "date": row.get("date", ""),
            "away_team": row.get("away_team", ""),
            "home_team": row.get("home_team", ""),
            "market_total": row.get("market_total", ""),
            "commence_time": row.get("commence_time", ""),
            "model_total": row.get("model_total", ""),
            "bet_side": row.get("best_side", ""),
            "edge_label": row.get("edge_label", ""),
            "best_ev": row.get("best_ev", ""),
            "odds": row.get("over_odds", "") if row.get("best_side") == "over" else row.get("under_odds", ""),
            "actual_total": row.get("actual_total", ""),
            "away_runs": row.get("away_runs", ""),
            "home_runs": row.get("home_runs", ""),
            "result": row.get("result", "pending") or "pending",
            "profit_units": row.get("profit_units", ""),
        }
        key = _pick_key(pick)
        if key not in by_key:
            by_key[key] = pick
            added += 1
        elif _is_open_pick(by_key[key]):
            by_key[key] = {
                **by_key[key],
                **pick,
                "actual_total": by_key[key].get("actual_total", ""),
                "away_runs": by_key[key].get("away_runs", ""),
                "home_runs": by_key[key].get("home_runs", ""),
                "result": by_key[key].get("result", "pending") or "pending",
                "profit_units": by_key[key].get("profit_units", ""),
            }
            updated += 1
    rows = sorted(by_key.values(), key=lambda row: (row.get("date", ""), row.get("away_team", ""), row.get("home_team", "")))
    write_csv(tracker_path, rows, TRACKER_COLUMNS)
    return added, updated, len(rows)


def grade_tracker(tracker_path: str, out: str | None = None) -> tuple[int, dict[str, object]]:
    rows = load_csv(tracker_path) if Path(tracker_path).exists() else []
    scores_by_date = _scores_for_dates(sorted({row["date"] for row in rows if row.get("date") and row.get("result", "pending") == "pending"}))
    graded = 0
    updated = []
    for row in rows:
        if row.get("result") and row.get("result") != "pending":
            updated.append(row)
            continue
        score = scores_by_date.get(_game_key(row))
        if score:
            row = _grade_row(row, score)
            graded += 1
        else:
            row = {**row, "result": row.get("result") or "pending"}
        updated.append(row)
    target = out or tracker_path
    write_csv(target, updated, TRACKER_COLUMNS)
    return graded, tracker_summary(updated)


def remove_picks_for_date(tracker_path: str, game_date: str) -> tuple[int, int]:
    rows = load_csv(tracker_path) if Path(tracker_path).exists() else []
    kept = [row for row in rows if row.get("date") != game_date]
    removed = len(rows) - len(kept)
    write_csv(tracker_path, kept, TRACKER_COLUMNS)
    return removed, len(kept)


def tracker_summary(rows: list[dict[str, str]]) -> dict[str, object]:
    settled = [row for row in rows if row.get("result") in {"win", "loss", "push"}]
    pending = [row for row in rows if row.get("result", "pending") == "pending"]
    wins = sum(1 for row in settled if row.get("result") == "win")
    losses = sum(1 for row in settled if row.get("result") == "loss")
    pushes = sum(1 for row in settled if row.get("result") == "push")
    profit = sum(float(row.get("profit_units") or 0) for row in settled)
    bets = len(settled)
    return {
        "tracked_picks": len(rows),
        "settled": bets,
        "pending": len(pending),
        "wins": wins,
        "losses": losses,
        "pushes": pushes,
        "profit_units": round(profit, 4),
        "roi": round(profit / bets, 4) if bets else 0,
    }


def write_tracker_report(tracker_path: str, out: str) -> dict[str, object]:
    rows = load_csv(tracker_path) if Path(tracker_path).exists() else []
    summary = tracker_summary(rows)
    lines = [
        "Daily Pick Tracker",
        "==================",
        "",
        f"Tracked picks: {summary['tracked_picks']}",
        f"Settled: {summary['settled']}",
        f"Pending: {summary['pending']}",
        f"Wins: {summary['wins']}",
        f"Losses: {summary['losses']}",
        f"Pushes: {summary['pushes']}",
        f"Profit: {summary['profit_units']} units",
        f"ROI: {float(summary['roi']):.2%}",
        "",
    ]
    Path(out).parent.mkdir(parents=True, exist_ok=True)
    Path(out).write_text("\n".join(lines))
    return summary


def _include_label(label: str, minimum: str) -> bool:
    rank = {"pass": 0, "lean": 1, "watch": 2}
    return rank.get(label, 0) >= rank.get(minimum, 1)


def _is_open_pick(row: dict[str, str]) -> bool:
    return row.get("result", "pending") in {"", "pending"}


def _scores_for_dates(dates: list[str]) -> dict[tuple[str, str, str], dict[str, int]]:
    scores = {}
    for game_date in dates:
        payload = fetch_mlb_schedule(game_date)
        for date_block in payload.get("dates", []):
            for game in date_block.get("games", []):
                status = game.get("status", {}).get("detailedState", "")
                away = game.get("teams", {}).get("away", {})
                home = game.get("teams", {}).get("home", {})
                row = {
                    "date": date_block.get("date", game_date),
                    "away_team": MLB_TEAM_CODES.get(away.get("team", {}).get("name", ""), away.get("team", {}).get("name", "")),
                    "home_team": MLB_TEAM_CODES.get(home.get("team", {}).get("name", ""), home.get("team", {}).get("name", "")),
                }
                if status in {"Postponed", "Cancelled", "Suspended"}:
                    scores[_game_key(row)] = {"result": "void"}
                    continue
                if status not in {"Final", "Game Over", "Completed Early"}:
                    continue
                if "score" not in away or "score" not in home:
                    continue
                scores[_game_key(row)] = {"away_runs": int(away["score"]), "home_runs": int(home["score"])}
    return scores


def _grade_row(row: dict[str, str], score: dict[str, int | str]) -> dict[str, str]:
    if score.get("result") == "void":
        return {
            **row,
            "actual_total": "",
            "away_runs": "",
            "home_runs": "",
            "result": "void",
            "profit_units": "0.0000",
        }

    away_runs = score["away_runs"]
    home_runs = score["home_runs"]
    actual_total = away_runs + home_runs
    market_total = float(row["market_total"])
    side = row["bet_side"]
    odds = float(row["odds"])
    if actual_total == market_total:
        result = "push"
        profit = 0.0
    elif side == "over" and actual_total > market_total:
        result = "win"
        profit = american_to_decimal(odds) - 1
    elif side == "under" and actual_total < market_total:
        result = "win"
        profit = american_to_decimal(odds) - 1
    else:
        result = "loss"
        profit = -1.0
    return {
        **row,
        "actual_total": str(actual_total),
        "away_runs": str(away_runs),
        "home_runs": str(home_runs),
        "result": result,
        "profit_units": f"{profit:.4f}",
    }


def _pick_key(row: dict[str, str]) -> tuple[str, str, str]:
    return (
        row.get("date", ""),
        row.get("away_team", ""),
        row.get("home_team", ""),
    )


def _game_key(row: dict[str, str]) -> tuple[str, str, str]:
    return (row.get("date", ""), row.get("away_team", ""), row.get("home_team", ""))
