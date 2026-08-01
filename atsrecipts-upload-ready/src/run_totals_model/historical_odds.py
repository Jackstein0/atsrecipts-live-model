from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
import json
import os
from pathlib import Path
from typing import Any
from urllib.parse import urlencode

from .features import load_games, write_csv
from .odds import MLB_TEAM_CODES, odds_columns, totals_payload_to_board


TEAM_ALIASES = {
    **MLB_TEAM_CODES,
    "ARI": "ARI",
    "ATH": "ATH",
    "ATL": "ATL",
    "BAL": "BAL",
    "BOS": "BOS",
    "CHC": "CHC",
    "CHW": "CHW",
    "CIN": "CIN",
    "CLE": "CLE",
    "COL": "COL",
    "DET": "DET",
    "HOU": "HOU",
    "KC": "KCR",
    "KCR": "KCR",
    "LAA": "LAA",
    "LAD": "LAD",
    "MIA": "MIA",
    "MIL": "MIL",
    "MIN": "MIN",
    "NYM": "NYM",
    "NYY": "NYY",
    "OAK": "ATH",
    "PHI": "PHI",
    "PIT": "PIT",
    "SD": "SDP",
    "SDP": "SDP",
    "SF": "SFG",
    "SFG": "SFG",
    "SEA": "SEA",
    "STL": "STL",
    "TB": "TBR",
    "TBR": "TBR",
    "TEX": "TEX",
    "TOR": "TOR",
    "WAS": "WSN",
    "WSH": "WSN",
    "WSN": "WSN",
    "Kansas City Royals": "KCR",
    "Tampa Bay Rays": "TBR",
}


def fetch_historical_totals_snapshot(
    snapshot_time: str,
    api_key: str | None = None,
    regions: str = "us",
    bookmakers: str | None = None,
    commence_from: str | None = None,
    commence_to: str | None = None,
) -> dict[str, Any]:
    import requests

    key = api_key or os.environ.get("THE_ODDS_API_KEY")
    if not key:
        raise ValueError("Missing API key.")

    params = {
        "apiKey": key,
        "regions": regions,
        "markets": "totals",
        "oddsFormat": "american",
        "dateFormat": "iso",
        "date": snapshot_time,
    }
    if bookmakers:
        params.pop("regions")
        params["bookmakers"] = bookmakers
    if commence_from:
        params["commenceTimeFrom"] = commence_from
    if commence_to:
        params["commenceTimeTo"] = commence_to

    url = f"https://api.the-odds-api.com/v4/historical/sports/baseball_mlb/odds/?{urlencode(params)}"
    response = requests.get(url, timeout=30)
    if response.status_code in {401, 402, 403}:
        raise PermissionError("Historical odds access is not enabled for this API key/plan.")
    response.raise_for_status()
    return response.json()


def test_historical_access(out_json: str = "data/raw/historical_access_test.json") -> bool:
    yesterday = date.today() - timedelta(days=1)
    start, end = _date_window(yesterday.isoformat())
    payload = fetch_historical_totals_snapshot(
        snapshot_time=f"{yesterday.isoformat()}T16:00:00Z",
        commence_from=start,
        commence_to=end,
    )
    Path(out_json).parent.mkdir(parents=True, exist_ok=True)
    Path(out_json).write_text(json.dumps(_redacted_payload(payload), indent=2, sort_keys=True))
    return True


def fetch_historical_totals_for_training(
    historical_games_path: str,
    odds_out: str,
    raw_dir: str = "data/raw/historical_odds",
    max_days: int = 7,
    snapshot_hour_utc: int = 16,
    regions: str = "us",
    bookmakers: str | None = None,
) -> list[dict[str, object]]:
    games = load_games(historical_games_path)
    dates = sorted({row["date"] for row in games if row.get("date")}, reverse=True)[:max_days]
    raw_path = Path(raw_dir)
    raw_path.mkdir(parents=True, exist_ok=True)
    odds_rows: list[dict[str, object]] = []

    for game_date in dates:
        start, end = _date_window(game_date)
        snapshot = f"{game_date}T{snapshot_hour_utc:02d}:00:00Z"
        payload = fetch_historical_totals_snapshot(
            snapshot_time=snapshot,
            regions=regions,
            bookmakers=bookmakers,
            commence_from=start,
            commence_to=end,
        )
        (raw_path / f"{game_date}.json").write_text(json.dumps(_redacted_payload(payload), indent=2, sort_keys=True))
        rows = totals_payload_to_board(payload.get("data", []))
        for row in rows:
            row["snapshot_time"] = payload.get("timestamp", snapshot)
            row["source"] = "the_odds_api_historical"
        odds_rows.extend(rows)

    columns = odds_columns(odds_rows)
    for extra in ["snapshot_time", "source"]:
        if extra not in columns:
            columns.append(extra)
    write_csv(odds_out, odds_rows, columns)
    return odds_rows


def apply_historical_odds(
    historical_games_path: str,
    historical_odds_path: str,
    out: str,
) -> tuple[int, int]:
    games = load_games(historical_games_path)
    odds_rows = _load_odds_rows(historical_odds_path)
    odds_by_key = {
        _game_key(row): row
        for row in odds_rows
    }
    matched = 0
    merged = []
    for row in games:
        odds = odds_by_key.get(_game_key(row))
        if odds:
            row = {
                **row,
                "market_total": odds["market_total"],
                "over_odds": odds["over_odds"],
                "under_odds": odds["under_odds"],
                "historical_odds_source": odds.get("source", "historical_odds_csv"),
            }
            matched += 1
        else:
            row = {**row, "historical_odds_source": row.get("historical_odds_source", "proxy")}
        merged.append(row)
    columns = list(merged[0].keys()) if merged else []
    write_csv(out, merged, columns)
    return matched, len(games)


def normalize_historical_odds_csv(input_path: str, out: str) -> tuple[int, list[str]]:
    rows = _load_odds_rows(input_path)
    normalized = []
    skipped_reasons = []
    for row in rows:
        try:
            parsed = _normalize_odds_row(row)
        except ValueError as error:
            skipped_reasons.append(str(error))
            continue
        normalized.append(parsed)
    write_csv(out, normalized, ["date", "away_team", "home_team", "market_total", "over_odds", "under_odds", "source"])
    return len(normalized), skipped_reasons


def write_historical_odds_template(
    historical_games_path: str,
    out: str,
) -> int:
    games = load_games(historical_games_path)
    rows = []
    seen = set()
    for game in games:
        key = _game_key(game)
        if key in seen:
            continue
        seen.add(key)
        rows.append({
            "date": game.get("date", ""),
            "away_team": game.get("away_team", ""),
            "home_team": game.get("home_team", ""),
            "market_total": "",
            "over_odds": "",
            "under_odds": "",
            "source": "",
        })
    write_csv(out, rows, ["date", "away_team", "home_team", "market_total", "over_odds", "under_odds", "source"])
    return len(rows)


def _normalize_odds_row(row: dict[str, str]) -> dict[str, object]:
    lowered = {key.strip().lower().replace(" ", "_"): value for key, value in row.items()}
    game_date = _first(lowered, "date", "game_date", "commence_date")
    away = _team_code(_first(lowered, "away_team", "away", "visitor", "visitor_team", "road_team"))
    home = _team_code(_first(lowered, "home_team", "home", "home_team_name"))
    total = _first(lowered, "market_total", "total", "closing_total", "close_total", "ou", "o/u", "over_under")
    over_odds = _first(lowered, "over_odds", "over", "over_price", "closing_over", "close_over")
    under_odds = _first(lowered, "under_odds", "under", "under_price", "closing_under", "close_under")

    if not game_date:
        raise ValueError("missing date")
    if not away or not home:
        raise ValueError("missing teams")
    if not total:
        raise ValueError("missing total")

    return {
        "date": _normalize_date(game_date),
        "away_team": away,
        "home_team": home,
        "market_total": _number(total),
        "over_odds": int(float(over_odds)) if over_odds else -110,
        "under_odds": int(float(under_odds)) if under_odds else -110,
        "source": _first(lowered, "source", "sportsbook", "book", default="imported_csv"),
    }


def _first(row: dict[str, str], *keys: str, default: str = "") -> str:
    for key in keys:
        value = row.get(key)
        if value not in (None, ""):
            return str(value).strip()
    return default


def _team_code(value: str) -> str:
    return TEAM_ALIASES.get(value.strip(), TEAM_ALIASES.get(value.strip().upper(), value.strip().upper()))


def _normalize_date(value: str) -> str:
    value = value.strip()
    if "/" in value:
        parts = value.split("/")
        if len(parts) == 3:
            month, day, year = parts
            if len(year) == 2:
                year = "20" + year
            return f"{int(year):04d}-{int(month):02d}-{int(day):02d}"
    return value[:10]


def _number(value: str) -> float:
    cleaned = value.strip().replace("o", "").replace("u", "").replace("O", "").replace("U", "")
    return float(cleaned)


def _load_odds_rows(path: str) -> list[dict[str, str]]:
    import csv

    with open(path, newline="") as handle:
        return list(csv.DictReader(handle))


def _date_window(game_date: str) -> tuple[str, str]:
    start = datetime.fromisoformat(game_date).replace(tzinfo=timezone.utc)
    end = start + timedelta(days=1, hours=8)
    return start.isoformat().replace("+00:00", "Z"), end.isoformat().replace("+00:00", "Z")


def _game_key(row: dict[str, object]) -> tuple[str, str, str]:
    return (str(row.get("date", "")), str(row.get("away_team", "")), str(row.get("home_team", "")))


def _redacted_payload(payload: dict[str, Any]) -> dict[str, Any]:
    return {
        "timestamp": payload.get("timestamp"),
        "previous_timestamp": payload.get("previous_timestamp"),
        "next_timestamp": payload.get("next_timestamp"),
        "data": payload.get("data", []),
    }
