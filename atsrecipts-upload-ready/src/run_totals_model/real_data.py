from __future__ import annotations

from collections import defaultdict
from datetime import date, timedelta
import json
from pathlib import Path
from typing import Any

from .features import write_csv
from .odds import MLB_TEAM_CODES
from .schedule import fetch_mlb_schedule, schedule_payload_to_games


PARK_FACTORS = {
    "ARI": 101,
    "ATH": 98,
    "ATL": 101,
    "BAL": 98,
    "BOS": 105,
    "CHC": 102,
    "CHW": 101,
    "CIN": 107,
    "CLE": 97,
    "COL": 116,
    "DET": 98,
    "HOU": 99,
    "KCR": 101,
    "LAA": 99,
    "LAD": 100,
    "MIA": 96,
    "MIL": 101,
    "MIN": 99,
    "NYM": 97,
    "NYY": 104,
    "PHI": 103,
    "PIT": 96,
    "SDP": 96,
    "SEA": 95,
    "SFG": 96,
    "STL": 98,
    "TBR": 98,
    "TEX": 103,
    "TOR": 101,
    "WSN": 100,
}


def update_real_data(
    game_date: str | None = None,
    lookback_days: int = 45,
    team_metrics: str = "data/source/team_metrics.csv",
    starter_metrics: str = "data/source/starter_metrics.csv",
    bullpen_metrics: str = "data/source/bullpen_metrics.csv",
    park_metrics: str = "data/source/park_metrics.csv",
    weather_metrics: str = "data/source/weather_metrics.csv",
    historical_games: str = "data/processed/historical_games.csv",
    raw_dir: str = "data/raw",
) -> None:
    target = date.fromisoformat(game_date) if game_date else date.today()
    start = target - timedelta(days=lookback_days)
    raw_path = Path(raw_dir)
    raw_path.mkdir(parents=True, exist_ok=True)

    history_payload = fetch_schedule_range(start.isoformat(), (target - timedelta(days=1)).isoformat())
    (raw_path / "recent_completed_schedule.json").write_text(json.dumps(history_payload, indent=2, sort_keys=True))
    today_payload = fetch_mlb_schedule(target.isoformat(), str(raw_path / "today_schedule.json"))

    completed_games = completed_games_from_schedule(history_payload)
    today_games = schedule_payload_to_games(today_payload)

    team_rows, team_lookup = build_team_metrics(completed_games)
    bullpen_rows, bullpen_lookup = build_bullpen_metrics(completed_games)
    starter_rows, starter_lookup = build_starter_metrics(today_games)
    park_rows = [{"team": team, "park_factor": factor} for team, factor in sorted(PARK_FACTORS.items())]
    weather_rows = [
        {"game_id": row["game_id"], "temp_f": "70", "wind_out_mph": "0"}
        for row in today_games
    ]
    historical_rows = build_historical_training_rows(completed_games, team_lookup, bullpen_lookup, starter_lookup)

    write_csv(team_metrics, team_rows, ["team", "wrc_plus"])
    write_csv(starter_metrics, starter_rows, ["mlbam_id", "pitcher_name", "xfip"])
    write_csv(bullpen_metrics, bullpen_rows, ["team", "bullpen_xfip"])
    write_csv(park_metrics, park_rows, ["team", "park_factor"])
    write_csv(weather_metrics, weather_rows, ["game_id", "temp_f", "wind_out_mph"])
    write_csv(historical_games, historical_rows, [
        "date",
        "away_team",
        "home_team",
        "away_runs",
        "home_runs",
        "market_total",
        "over_odds",
        "under_odds",
        "home_wrc_plus",
        "away_wrc_plus",
        "home_sp_xfip",
        "away_sp_xfip",
        "home_bullpen_xfip",
        "away_bullpen_xfip",
        "park_factor",
        "temp_f",
        "wind_out_mph",
    ])


def fetch_schedule_range(start_date: str, end_date: str) -> dict[str, Any]:
    import requests

    url = (
        "https://statsapi.mlb.com/api/v1/schedule"
        f"?sportId=1&startDate={start_date}&endDate={end_date}&hydrate=probablePitcher,venue"
    )
    response = requests.get(url, timeout=30)
    response.raise_for_status()
    return response.json()


def completed_games_from_schedule(payload: dict[str, Any]) -> list[dict[str, object]]:
    games = []
    for date_block in payload.get("dates", []):
        game_date = date_block.get("date", "")
        for game in date_block.get("games", []):
            status = game.get("status", {}).get("detailedState", "")
            if status not in {"Final", "Game Over", "Completed Early"}:
                continue
            away = game.get("teams", {}).get("away", {})
            home = game.get("teams", {}).get("home", {})
            if "score" not in away or "score" not in home:
                continue
            venue = game.get("venue", {})
            away_pitcher = away.get("probablePitcher", {})
            home_pitcher = home.get("probablePitcher", {})
            away_team = _team_code(away.get("team", {}).get("name", ""))
            home_team = _team_code(home.get("team", {}).get("name", ""))
            games.append({
                "date": game_date,
                "away_team": away_team,
                "home_team": home_team,
                "away_runs": int(away["score"]),
                "home_runs": int(home["score"]),
                "away_sp_id": str(away_pitcher.get("id", "")),
                "home_sp_id": str(home_pitcher.get("id", "")),
                "away_sp_name": away_pitcher.get("fullName", ""),
                "home_sp_name": home_pitcher.get("fullName", ""),
                "venue_name": venue.get("name", ""),
            })
    return games


def build_team_metrics(games: list[dict[str, object]]) -> tuple[list[dict[str, object]], dict[str, float]]:
    runs = defaultdict(int)
    games_played = defaultdict(int)
    for game in games:
        away = str(game["away_team"])
        home = str(game["home_team"])
        runs[away] += int(game["away_runs"])
        runs[home] += int(game["home_runs"])
        games_played[away] += 1
        games_played[home] += 1
    league_rpg = sum(runs.values()) / max(sum(games_played.values()), 1)
    lookup = {}
    rows = []
    for team in sorted(games_played):
        rpg = runs[team] / max(games_played[team], 1)
        wrc_plus = round(100 * rpg / league_rpg, 1) if league_rpg else 100.0
        lookup[team] = wrc_plus
        rows.append({"team": team, "wrc_plus": wrc_plus})
    return rows, lookup


def build_bullpen_metrics(games: list[dict[str, object]]) -> tuple[list[dict[str, object]], dict[str, float]]:
    runs_allowed = defaultdict(int)
    games_played = defaultdict(int)
    for game in games:
        away = str(game["away_team"])
        home = str(game["home_team"])
        runs_allowed[away] += int(game["home_runs"])
        runs_allowed[home] += int(game["away_runs"])
        games_played[away] += 1
        games_played[home] += 1
    lookup = {}
    rows = []
    for team in sorted(games_played):
        # This is team runs allowed per game, used as a real-data proxy until
        # a true FanGraphs bullpen xFIP export is supplied.
        value = round(runs_allowed[team] / max(games_played[team], 1), 2)
        lookup[team] = value
        rows.append({"team": team, "bullpen_xfip": value})
    return rows, lookup


def build_starter_metrics(today_games: list[dict[str, object]]) -> tuple[list[dict[str, object]], dict[str, float]]:
    rows = []
    lookup = {}
    for game in today_games:
        for side in ("away", "home"):
            pitcher_id = str(game.get(f"{side}_sp_id", ""))
            pitcher_name = str(game.get(f"{side}_sp_name", ""))
            if not pitcher_id and not pitcher_name:
                continue
            era = fetch_pitcher_era(pitcher_id) if pitcher_id else 4.20
            rows.append({"mlbam_id": pitcher_id, "pitcher_name": pitcher_name, "xfip": era})
            if pitcher_id:
                lookup[pitcher_id] = era
    return rows, lookup


def fetch_pitcher_era(pitcher_id: str) -> float:
    import requests

    try:
        url = f"https://statsapi.mlb.com/api/v1/people/{pitcher_id}/stats?stats=season&group=pitching"
        response = requests.get(url, timeout=15)
        response.raise_for_status()
        splits = response.json().get("stats", [{}])[0].get("splits", [])
        if not splits:
            return 4.20
        return round(float(splits[0].get("stat", {}).get("era", 4.20)), 2)
    except Exception:
        return 4.20


def build_historical_training_rows(
    games: list[dict[str, object]],
    team_lookup: dict[str, float],
    bullpen_lookup: dict[str, float],
    starter_lookup: dict[str, float],
) -> list[dict[str, object]]:
    rows = []
    team_runs = defaultdict(int)
    team_allowed = defaultdict(int)
    team_games = defaultdict(int)
    league_runs = 0
    league_team_games = 0

    for game in sorted(games, key=lambda row: str(row.get("date", ""))):
        away = str(game["away_team"])
        home = str(game["home_team"])
        league_rpg = league_runs / league_team_games if league_team_games else 4.5
        away_rpg = team_runs[away] / team_games[away] if team_games[away] else league_rpg
        home_rpg = team_runs[home] / team_games[home] if team_games[home] else league_rpg
        away_allowed = team_allowed[away] / team_games[away] if team_games[away] else league_rpg
        home_allowed = team_allowed[home] / team_games[home] if team_games[home] else league_rpg
        away_wrc = 100 * away_rpg / league_rpg if league_rpg else 100.0
        home_wrc = 100 * home_rpg / league_rpg if league_rpg else 100.0
        market_total = ((away_rpg + home_rpg + away_allowed + home_allowed) / 2) * (PARK_FACTORS.get(home, 100) / 100)
        rows.append({
            "date": game["date"],
            "away_team": away,
            "home_team": home,
            "away_runs": game["away_runs"],
            "home_runs": game["home_runs"],
            "market_total": max(6.5, min(12.5, round(market_total * 2) / 2)),
            "over_odds": -110,
            "under_odds": -110,
            "home_wrc_plus": round(home_wrc, 1),
            "away_wrc_plus": round(away_wrc, 1),
            "home_sp_xfip": starter_lookup.get(str(game.get("home_sp_id", "")), 4.20),
            "away_sp_xfip": starter_lookup.get(str(game.get("away_sp_id", "")), 4.20),
            "home_bullpen_xfip": round(home_allowed, 2),
            "away_bullpen_xfip": round(away_allowed, 2),
            "park_factor": PARK_FACTORS.get(home, 100),
            "temp_f": 70,
            "wind_out_mph": 0,
        })
        away_runs = int(game["away_runs"])
        home_runs = int(game["home_runs"])
        team_runs[away] += away_runs
        team_runs[home] += home_runs
        team_allowed[away] += home_runs
        team_allowed[home] += away_runs
        team_games[away] += 1
        team_games[home] += 1
        league_runs += away_runs + home_runs
        league_team_games += 2
    return rows


def _team_code(name: str) -> str:
    return MLB_TEAM_CODES.get(name, name)
