from __future__ import annotations

from datetime import date, datetime, timedelta
from html import escape
from pathlib import Path
import shutil

from .features import load_csv, write_csv
from .odds import MLB_TEAM_CODES
from .schedule import fetch_mlb_schedule


GAME_COLUMNS = [
    "date",
    "away_team",
    "home_team",
    "away_runs",
    "home_runs",
    "total_runs",
    "status",
]


def document_games(
    game_date: str | None = None,
    out_csv: str = "data/processed/yesterday_games.csv",
    out_html: str = "data/processed/yesterday_games.html",
    tracker_path: str = "data/processed/pick_tracker.csv",
) -> tuple[int, int]:
    target_date = game_date or (date.today() - timedelta(days=1)).isoformat()
    payload = fetch_mlb_schedule(target_date)
    games = _games_from_payload(payload, target_date)
    picks = _picks_for_date(tracker_path, target_date)
    write_csv(out_csv, games, GAME_COLUMNS)
    _write_html(target_date, games, picks, out_html)
    return len(games), len(picks)


def archive_current_outputs(results_path: str = "data/processed/today_results.csv", report_path: str = "data/processed/today_report.html") -> list[str]:
    archived = []
    rows = load_csv(results_path) if Path(results_path).exists() else []
    archive_date = rows[0].get("date") if rows else date.today().isoformat()
    archive_dir = Path("data/archive") / archive_date / datetime.now().strftime("%H%M%S")
    archive_dir.mkdir(parents=True, exist_ok=True)
    for source in [results_path, report_path, "data/processed/today_board.csv", "data/processed/today_features.csv"]:
        source_path = Path(source)
        if source_path.exists():
            target = archive_dir / source_path.name
            shutil.copyfile(source_path, target)
            archived.append(str(target))
    return archived


def _games_from_payload(payload: dict, fallback_date: str) -> list[dict[str, object]]:
    rows = []
    for date_block in payload.get("dates", []):
        game_date = date_block.get("date", fallback_date)
        for game in date_block.get("games", []):
            away = game.get("teams", {}).get("away", {})
            home = game.get("teams", {}).get("home", {})
            away_runs = away.get("score", "")
            home_runs = home.get("score", "")
            total_runs = int(away_runs) + int(home_runs) if away_runs != "" and home_runs != "" else ""
            rows.append({
                "date": game_date,
                "away_team": MLB_TEAM_CODES.get(away.get("team", {}).get("name", ""), away.get("team", {}).get("name", "")),
                "home_team": MLB_TEAM_CODES.get(home.get("team", {}).get("name", ""), home.get("team", {}).get("name", "")),
                "away_runs": away_runs,
                "home_runs": home_runs,
                "total_runs": total_runs,
                "status": game.get("status", {}).get("detailedState", ""),
            })
    return rows


def _picks_for_date(tracker_path: str, game_date: str) -> list[dict[str, str]]:
    if not Path(tracker_path).exists():
        return []
    return [row for row in load_csv(tracker_path) if row.get("date") == game_date]


def _write_html(game_date: str, games: list[dict[str, object]], picks: list[dict[str, str]], out: str) -> None:
    game_rows = "\n".join(
        f"<tr><td>{escape(str(row['away_team']))} @ {escape(str(row['home_team']))}</td>"
        f"<td>{escape(str(row['away_runs']))}-{escape(str(row['home_runs']))}</td>"
        f"<td>{escape(str(row['total_runs']))}</td><td>{escape(str(row['status']))}</td></tr>"
        for row in games
    )
    pick_rows = "\n".join(
        f"<tr><td>{escape(row.get('away_team', ''))} @ {escape(row.get('home_team', ''))}</td>"
        f"<td>{escape(row.get('bet_side', ''))} {escape(row.get('market_total', ''))}</td>"
        f"<td>{escape(row.get('result', ''))}</td><td>{escape(row.get('profit_units', ''))}</td></tr>"
        for row in picks
    ) or "<tr><td colspan=\"4\">No tracked picks were preserved for this date.</td></tr>"
    html = f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>MLB Games {escape(game_date)}</title>
  <style>
    body {{ margin: 0; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; background: #f6f7f9; color: #1d2329; }}
    header {{ padding: 24px; background: #17202a; color: white; }}
    main {{ max-width: 1000px; margin: 0 auto; padding: 20px; }}
    section {{ background: white; border: 1px solid #dfe3e8; border-radius: 8px; margin-bottom: 14px; padding: 14px; }}
    table {{ width: 100%; border-collapse: collapse; }}
    th, td {{ text-align: left; border-bottom: 1px solid #eef1f4; padding: 8px; }}
    th {{ background: #f0f3f6; }}
  </style>
</head>
<body>
  <header><h1>MLB Games {escape(game_date)}</h1></header>
  <main>
    <section>
      <h2>Final Scores</h2>
      <table><thead><tr><th>Game</th><th>Score</th><th>Total Runs</th><th>Status</th></tr></thead><tbody>{game_rows}</tbody></table>
    </section>
    <section>
      <h2>Tracked Picks</h2>
      <table><thead><tr><th>Game</th><th>Pick</th><th>Result</th><th>Units</th></tr></thead><tbody>{pick_rows}</tbody></table>
    </section>
  </main>
</body>
</html>
"""
    Path(out).parent.mkdir(parents=True, exist_ok=True)
    Path(out).write_text(html)
