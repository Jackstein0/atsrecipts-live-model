from __future__ import annotations

from datetime import date, datetime, timezone
from html import escape
from pathlib import Path

from .features import load_csv


def write_today_html(
    results_path: str,
    out: str,
    backtest_path: str | None = None,
    tracker_path: str = "data/processed/pick_tracker.csv",
    features_path: str = "data/processed/today_features.csv",
) -> None:
    rows = _dedupe_games(load_csv(results_path))
    all_tracked_rows = _all_tracked_rows(tracker_path)
    tracked_rows = _tracked_rows(tracker_path, rows)
    coverage_rows = _coverage_rows(features_path, rows, tracked_rows)
    backtest = Path(backtest_path).read_text() if backtest_path and Path(backtest_path).exists() else ""
    cards = "\n".join(_card(row) for row in rows)
    html = f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>MLB Run Totals Report</title>
  <style>
    body {{
      margin: 0;
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      background:
        radial-gradient(circle at 18% 12%, rgba(255, 197, 47, 0.20), transparent 28%),
        radial-gradient(circle at 82% 18%, rgba(255, 197, 47, 0.12), transparent 24%),
        linear-gradient(135deg, #102d59 0%, #1c3d70 48%, #0d2448 100%);
      background-attachment: fixed;
      color: #1d2329;
      min-height: 100vh;
    }}
    body::before {{
      content: "";
      position: fixed;
      inset: 0;
      z-index: 0;
      background: url("assets/brewers-logo-wallpaper.png") center 80px / min(72vw, 860px) auto no-repeat fixed;
      opacity: 0.16;
      pointer-events: none;
    }}
    header, main {{ position: relative; z-index: 1; }}
    header {{ padding: 24px; background: rgba(7, 26, 54, 0.92); color: white; border-bottom: 4px solid #ffc52f; }}
    main {{ max-width: 1120px; margin: 0 auto; padding: 20px; }}
    .grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(280px, 1fr)); gap: 12px; }}
    .card {{ background: rgba(255, 255, 255, 0.97); border: 1px solid #dfe3e8; border-radius: 8px; padding: 14px; }}
    .teams {{ font-size: 18px; font-weight: 700; margin-bottom: 8px; }}
    .meta {{ color: #52606d; font-size: 13px; margin-bottom: 12px; }}
    .pick {{ display: inline-block; padding: 4px 8px; border-radius: 999px; font-weight: 700; }}
    .watch {{ background: #fff1c2; color: #5c4300; }}
    .lean {{ background: #dff5e8; color: #135c31; }}
    .pass {{ background: #edf0f3; color: #52606d; }}
    table {{ width: 100%; border-collapse: collapse; margin-top: 10px; }}
    th, td {{ padding: 6px 8px; border-bottom: 1px solid #eef1f4; font-size: 14px; text-align: left; }}
    td:last-child {{ font-variant-numeric: tabular-nums; }}
    .card td {{ padding: 4px 0; }}
    .card td:last-child {{ text-align: right; }}
    .tracker {{ background: rgba(255, 255, 255, 0.97); border: 1px solid #dfe3e8; border-radius: 8px; margin-top: 16px; padding: 14px; overflow-x: auto; }}
    .tracker h2 {{ margin: 0 0 8px; }}
    main > h2, main > p {{ color: white; text-shadow: 0 1px 2px rgba(0, 0, 0, 0.45); }}
    pre {{ white-space: pre-wrap; background: #111820; color: #f4f7fa; padding: 14px; border-radius: 8px; }}
  </style>
</head>
<body>
  <header>
    <h1>MLB Run Totals Report</h1>
    <div>Generated {escape(datetime.now().strftime("%Y-%m-%d %H:%M"))}</div>
  </header>
  <main>
    <p>This is a research report, not betting advice. Watch and lean are tracked; pass is shown for context only.</p>
    {_record_block(all_tracked_rows)}
    {_coverage_block(coverage_rows)}
    <h2>Full Model Board</h2>
    <section class="grid">{cards}</section>
    {_tracker_block(tracked_rows)}
    {_backtest_block(backtest)}
  </main>
</body>
</html>
"""
    target = Path(out)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(html)


def _card(row: dict[str, str]) -> str:
    label = row.get("edge_label", "pass")
    pick_text = f"{label.upper()}: {row.get('best_side', '').upper()}"
    if label == "pass":
        pick_text = f"NOT TRACKED: PASS {row.get('best_side', '').upper()}"
    return f"""
<article class="card">
  <div class="teams">{escape(row.get("away_team", ""))} @ {escape(row.get("home_team", ""))}</div>
  <div class="meta">{escape(row.get("date", ""))} · total {escape(row.get("market_total", ""))}</div>
  <div class="pick {escape(label)}">{escape(pick_text)}</div>
  <table>
    <tr><td>Model total</td><td>{_num(row.get("model_total"))}</td></tr>
    <tr><td>Best EV</td><td>{_pct(row.get("best_ev"))}</td></tr>
    <tr><td>Over probability</td><td>{_pct(row.get("over_probability"))}</td></tr>
    <tr><td>Under probability</td><td>{_pct(row.get("under_probability"))}</td></tr>
    <tr><td>Weather</td><td>{_weather(row)}</td></tr>
    <tr><td>Sportsbook</td><td>{escape(row.get("sportsbook", ""))}</td></tr>
  </table>
</article>
"""


def _tracked_rows(tracker_path: str, current_rows: list[dict[str, str]]) -> list[dict[str, str]]:
    path = Path(tracker_path)
    if not path.exists():
        return []
    rows = _all_tracked_rows(tracker_path)
    dates = {row.get("date", "") for row in current_rows if row.get("date")}
    if not dates:
        dates = {date.today().isoformat()}
    return sorted(
        [row for row in rows if row.get("date") in dates],
        key=lambda row: (row.get("commence_time", ""), row.get("away_team", ""), row.get("home_team", "")),
    )


def _all_tracked_rows(tracker_path: str) -> list[dict[str, str]]:
    path = Path(tracker_path)
    return load_csv(str(path)) if path.exists() else []


def _coverage_rows(
    features_path: str,
    current_rows: list[dict[str, str]],
    tracked_rows: list[dict[str, str]],
) -> list[dict[str, str]]:
    path = Path(features_path)
    if not path.exists():
        return []
    current_by_game = {_game_key(row): row for row in current_rows}
    tracked_by_game = {_game_key(row): row for row in tracked_rows}
    rows = []
    for feature in load_csv(str(path)):
        key = _game_key(feature)
        current = current_by_game.get(key)
        tracked = tracked_by_game.get(key)
        if tracked:
            status = f"saved pick: {tracked.get('bet_side', '').upper()} {tracked.get('market_total', '')}".strip()
        elif current:
            label = current.get("edge_label", "pass").upper()
            side = current.get("best_side", "").upper()
            total = current.get("market_total", "")
            prefix = "not tracked: " if label == "PASS" else "available: "
            status = f"{prefix}{label} {side} {total}".strip()
        elif _has_started(feature.get("commence_time", "")):
            status = "started, no tracked pick"
        else:
            status = "no current total"
        rows.append({**feature, "coverage_status": status})
    return sorted(rows, key=lambda row: row.get("commence_time", ""))


def _coverage_block(rows: list[dict[str, str]]) -> str:
    body = "\n".join(
        "<tr>"
        f"<td>{escape(row.get('away_team', ''))} @ {escape(row.get('home_team', ''))}</td>"
        f"<td>{_local_time(row.get('commence_time', ''))}</td>"
        f"<td>{escape(row.get('coverage_status', ''))}</td>"
        "</tr>"
        for row in rows
    )
    if not body:
        body = "<tr><td colspan=\"3\">No schedule rows found for this slate.</td></tr>"
    return f"""
<section class="tracker">
  <h2>All Games</h2>
  <table>
    <thead><tr><th>Game</th><th>Start</th><th>Status</th></tr></thead>
    <tbody>{body}</tbody>
  </table>
</section>
"""


def _record_block(rows: list[dict[str, str]]) -> str:
    summary = _record_summary(rows)
    daily_rows = _daily_record_rows(rows)
    daily_body = "\n".join(
        "<tr>"
        f"<td>{escape(row['date'])}</td>"
        f"<td>{row['wins']}-{row['losses']}-{row['pushes']}</td>"
        f"<td>{row['pending']}</td>"
        f"<td>{row['profit_units']:.2f}</td>"
        f"<td>{row['roi']:.1%}</td>"
        "</tr>"
        for row in daily_rows
    )
    if not daily_body:
        daily_body = "<tr><td colspan=\"5\">No tracked picks yet.</td></tr>"
    return f"""
<section class="tracker">
  <h2>Running Record</h2>
  <table>
    <thead><tr><th>Tracked</th><th>Settled</th><th>Record</th><th>Pending</th><th>Units</th><th>ROI</th></tr></thead>
    <tbody><tr><td>{summary['tracked']}</td><td>{summary['settled']}</td><td>{summary['wins']}-{summary['losses']}-{summary['pushes']}</td><td>{summary['pending']}</td><td>{summary['profit_units']:.2f}</td><td>{summary['roi']:.1%}</td></tr></tbody>
  </table>
  <table>
    <thead><tr><th>Date</th><th>Record</th><th>Pending</th><th>Units</th><th>ROI</th></tr></thead>
    <tbody>{daily_body}</tbody>
  </table>
</section>
"""


def _tracker_block(rows: list[dict[str, str]]) -> str:
    body = "\n".join(
        "<tr>"
        f"<td>{escape(row.get('away_team', ''))} @ {escape(row.get('home_team', ''))}</td>"
        f"<td>{escape(row.get('bet_side', '').upper())} {escape(row.get('market_total', ''))}</td>"
        f"<td>{escape(row.get('edge_label', '').upper())}</td>"
        f"<td>{_pct(row.get('best_ev'))}</td>"
        f"<td>{escape(row.get('odds', ''))}</td>"
        f"<td>{escape(row.get('result', 'pending') or 'pending')}</td>"
        "</tr>"
        for row in rows
    )
    if not body:
        body = "<tr><td colspan=\"6\">No tracked picks for this slate yet.</td></tr>"
    return f"""
<section class="tracker">
  <h2>Tracked Picks</h2>
  <table>
    <thead><tr><th>Game</th><th>Pick</th><th>Label</th><th>EV</th><th>Odds</th><th>Status</th></tr></thead>
    <tbody>{body}</tbody>
  </table>
</section>
"""


def _record_summary(rows: list[dict[str, str]]) -> dict[str, float | int]:
    settled = [row for row in rows if row.get("result") in {"win", "loss", "push"}]
    wins = sum(1 for row in settled if row.get("result") == "win")
    losses = sum(1 for row in settled if row.get("result") == "loss")
    pushes = sum(1 for row in settled if row.get("result") == "push")
    profit = sum(_float(row.get("profit_units")) or 0 for row in settled)
    return {
        "tracked": len(rows),
        "settled": len(settled),
        "pending": sum(1 for row in rows if row.get("result", "pending") == "pending"),
        "wins": wins,
        "losses": losses,
        "pushes": pushes,
        "profit_units": profit,
        "roi": profit / len(settled) if settled else 0,
    }


def _daily_record_rows(rows: list[dict[str, str]]) -> list[dict[str, float | int | str]]:
    by_date: dict[str, list[dict[str, str]]] = {}
    for row in rows:
        by_date.setdefault(row.get("date", ""), []).append(row)
    summaries = []
    for game_date, date_rows in sorted(by_date.items(), reverse=True):
        summary = _record_summary(date_rows)
        summaries.append({"date": game_date, **summary})
    return summaries


def _dedupe_games(rows: list[dict[str, str]]) -> list[dict[str, str]]:
    by_game: dict[tuple[str, str, str], dict[str, str]] = {}
    for row in rows:
        key = (row.get("date", ""), row.get("away_team", ""), row.get("home_team", ""))
        current = by_game.get(key)
        row_ev = _float(row.get("best_ev")) or 0
        current_ev = _float(current.get("best_ev")) if current else None
        if current is None or row_ev > (current_ev or 0):
            by_game[key] = row
    return sorted(by_game.values(), key=lambda row: float(row.get("best_ev") or 0), reverse=True)


def _backtest_block(text: str) -> str:
    if not text:
        return ""
    return f"<h2>Backtest</h2><pre>{escape(text)}</pre>"


def _num(value: str | None) -> str:
    try:
        return f"{float(value):.2f}"
    except (TypeError, ValueError):
        return ""


def _pct(value: str | None) -> str:
    try:
        return f"{float(value):.1%}"
    except (TypeError, ValueError):
        return ""


def _weather(row: dict[str, str]) -> str:
    temp = _num(row.get("temp_f"))
    wind = _num(row.get("wind_mph"))
    direction = _num(row.get("wind_dir_degrees"))
    out_value = _float(row.get("wind_out_mph"))
    roof = row.get("roof", "")
    parts = []
    if temp:
        parts.append(f"{temp} F")
    if wind:
        parts.append(f"{wind} mph from {direction} deg")
    if out_value is not None:
        if out_value >= 0:
            parts.append(f"out {out_value:.1f}")
        else:
            parts.append(f"in {abs(out_value):.1f}")
    if roof:
        parts.append(f"roof {roof}")
    return escape(", ".join(parts))


def write_data_audit_html(root: str, out: str) -> None:
    root_path = Path(root)
    sections = [
        _file_section(root_path, "Team Metrics", "data/source/team_metrics.csv", 12),
        _file_section(root_path, "Starter Metrics", "data/source/starter_metrics.csv", 12),
        _file_section(root_path, "Bullpen Metrics", "data/source/bullpen_metrics.csv", 12),
        _file_section(root_path, "Park Factors", "data/source/park_metrics.csv", 12),
        _file_section(root_path, "Weather Metrics", "data/source/weather_metrics.csv", 13),
        _file_section(root_path, "Today Features", "data/processed/today_features.csv", 13),
        _file_section(root_path, "Current Odds Board", "data/processed/today_board.csv", 13),
        _file_section(root_path, "Final Priced Results", "data/processed/today_results.csv", 13),
        _file_section(root_path, "Historical Training Rows", "data/processed/historical_games.csv", 12),
        _file_section(root_path, "FanGraphs Team Export Drop Zone", "data/fangraphs/team_batting.csv", 8),
        _file_section(root_path, "FanGraphs Starters Export Drop Zone", "data/fangraphs/starters.csv", 8),
        _file_section(root_path, "FanGraphs Bullpen Export Drop Zone", "data/fangraphs/bullpen.csv", 8),
    ]
    html = f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>MLB Totals Data Audit</title>
  <style>
    body {{ margin: 0; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; background: #f6f7f9; color: #1d2329; }}
    header {{ padding: 24px; background: #17202a; color: white; }}
    main {{ max-width: 1180px; margin: 0 auto; padding: 20px; }}
    section {{ background: white; border: 1px solid #dfe3e8; border-radius: 8px; margin-bottom: 14px; padding: 14px; overflow-x: auto; }}
    h2 {{ margin: 0 0 4px; font-size: 18px; }}
    .meta {{ color: #52606d; font-size: 13px; margin-bottom: 10px; }}
    table {{ border-collapse: collapse; width: 100%; font-size: 13px; }}
    th, td {{ border-bottom: 1px solid #eef1f4; padding: 6px 8px; text-align: left; white-space: nowrap; }}
    th {{ background: #f0f3f6; }}
    .missing {{ color: #8a4b00; }}
  </style>
</head>
<body>
  <header>
    <h1>MLB Totals Data Audit</h1>
    <div>Generated {escape(datetime.now().strftime("%Y-%m-%d %H:%M"))}</div>
  </header>
  <main>
    <p>This shows the actual files feeding the model and report. FanGraphs drop-zone files may be empty templates until you replace them with exports.</p>
    {''.join(sections)}
  </main>
</body>
</html>
"""
    target = Path(out)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(html)


def _file_section(root: Path, title: str, relative_path: str, limit: int) -> str:
    path = root / relative_path
    if not path.exists():
        return f"<section><h2>{escape(title)}</h2><div class=\"meta missing\">Missing: {escape(relative_path)}</div></section>"
    rows = load_csv(str(path))
    columns = list(rows[0].keys()) if rows else _header_only(path)
    return f"""
<section>
  <h2>{escape(title)}</h2>
  <div class="meta">{escape(relative_path)} · {len(rows)} rows</div>
  {_table(rows[:limit], columns)}
</section>
"""


def _header_only(path: Path) -> list[str]:
    first = path.read_text().splitlines()[0:1]
    return first[0].split(",") if first else []


def _table(rows: list[dict[str, str]], columns: list[str]) -> str:
    if not columns:
        return "<div class=\"meta\">No columns found.</div>"
    header = "".join(f"<th>{escape(column)}</th>" for column in columns)
    body = "".join(
        "<tr>" + "".join(f"<td>{escape(str(row.get(column, '')))}</td>" for column in columns) + "</tr>"
        for row in rows
    )
    if not body:
        body = f"<tr><td colspan=\"{len(columns)}\">No data rows yet.</td></tr>"
    return f"<table><thead><tr>{header}</tr></thead><tbody>{body}</tbody></table>"


def _float(value: str | None) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _game_key(row: dict[str, str]) -> tuple[str, str, str]:
    return (row.get("date", ""), row.get("away_team", ""), row.get("home_team", ""))


def _has_started(value: str) -> bool:
    if not value:
        return False
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(timezone.utc) <= datetime.now(timezone.utc)
    except ValueError:
        return False


def _local_time(value: str) -> str:
    if not value:
        return ""
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone().strftime("%-I:%M %p")
    except ValueError:
        return value
