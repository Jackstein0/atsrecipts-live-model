from __future__ import annotations

from typing import Any

from .features import load_csv, write_csv
from .schedule import fetch_mlb_schedule, load_schedule_json, schedule_payload_to_games


FEATURE_COLUMNS = [
    "date",
    "away_team",
    "home_team",
    "home_wrc_plus",
    "away_wrc_plus",
    "home_sp_xfip",
    "away_sp_xfip",
    "home_bullpen_xfip",
    "away_bullpen_xfip",
    "park_factor",
    "temp_f",
    "wind_out_mph",
    "wind_mph",
    "wind_dir_degrees",
    "roof",
    "home_sp_name",
    "away_sp_name",
    "venue_name",
    "game_id",
    "commence_time",
]


def build_today_features(
    game_date: str | None,
    out: str,
    team_metrics: str,
    starter_metrics: str,
    bullpen_metrics: str,
    park_metrics: str,
    weather_metrics: str | None = None,
    schedule_json: str | None = None,
    raw_schedule_json: str | None = None,
) -> list[dict[str, object]]:
    payload = load_schedule_json(schedule_json) if schedule_json else fetch_mlb_schedule(game_date, raw_schedule_json)
    games = schedule_payload_to_games(payload)
    teams = _index_rows(load_csv(team_metrics), "team")
    starters_by_id = _index_rows(load_csv(starter_metrics), "mlbam_id")
    starters_by_name = _index_rows(load_csv(starter_metrics), "pitcher_name")
    bullpens = _index_rows(load_csv(bullpen_metrics), "team")
    parks = _index_rows(load_csv(park_metrics), "team")
    weather = _index_rows(load_csv(weather_metrics), "game_id") if weather_metrics else {}

    rows = []
    for game in games:
        home_team = str(game["home_team"])
        away_team = str(game["away_team"])
        home_starter = _starter_row(starters_by_id, starters_by_name, game.get("home_sp_id"), game.get("home_sp_name"))
        away_starter = _starter_row(starters_by_id, starters_by_name, game.get("away_sp_id"), game.get("away_sp_name"))
        park = parks.get(home_team, {})
        weather_row = weather.get(str(game.get("game_id", "")), {})
        rows.append({
            **game,
            "home_wrc_plus": _value(teams.get(home_team, {}), "wrc_plus"),
            "away_wrc_plus": _value(teams.get(away_team, {}), "wrc_plus"),
            "home_sp_xfip": _value(home_starter, "sp_xfip", "xfip"),
            "away_sp_xfip": _value(away_starter, "sp_xfip", "xfip"),
            "home_bullpen_xfip": _value(bullpens.get(home_team, {}), "bullpen_xfip", "xfip"),
            "away_bullpen_xfip": _value(bullpens.get(away_team, {}), "bullpen_xfip", "xfip"),
            "park_factor": _value(park, "park_factor"),
            "temp_f": _value(weather_row, "temp_f", default="70"),
            "wind_out_mph": _value(weather_row, "wind_out_mph", default="0"),
            "wind_mph": _value(weather_row, "wind_mph", default="0"),
            "wind_dir_degrees": _value(weather_row, "wind_dir_degrees", default="0"),
            "roof": _value(weather_row, "roof", default="unknown"),
        })

    write_csv(out, rows, FEATURE_COLUMNS)
    return rows


def _index_rows(rows: list[dict[str, str]], key: str) -> dict[str, dict[str, str]]:
    return {str(row.get(key, "")): row for row in rows if row.get(key, "") != ""}


def _starter_row(
    by_id: dict[str, dict[str, str]],
    by_name: dict[str, dict[str, str]],
    pitcher_id: Any,
    pitcher_name: Any,
) -> dict[str, str]:
    return by_id.get(str(pitcher_id), {}) or by_name.get(str(pitcher_name), {})


def _value(row: dict[str, str], *keys: str, default: str = "") -> str:
    for key in keys:
        value = row.get(key)
        if value not in (None, ""):
            return value
    return default
