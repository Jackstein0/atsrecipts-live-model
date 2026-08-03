from __future__ import annotations

from datetime import date, timedelta
import json
from pathlib import Path
from typing import Any
from urllib.parse import urlencode

from .odds import MLB_TEAM_CODES


FINAL_STATES = {"Final", "Game Over", "Completed Early", "Postponed", "Cancelled", "Suspended"}


def fetch_mlb_schedule(game_date: str | None = None, out_json: str | None = None) -> dict[str, Any]:
    import requests

    target_date = game_date or date.today().isoformat()
    payload = _fetch_schedule_payload(requests, target_date)
    if game_date is None and _slate_is_complete(payload):
        tomorrow = (date.fromisoformat(target_date) + timedelta(days=1)).isoformat()
        tomorrow_payload = _fetch_schedule_payload(requests, tomorrow)
        if tomorrow_payload.get("dates"):
            target_date = tomorrow
            payload = tomorrow_payload
    if out_json:
        Path(out_json).parent.mkdir(parents=True, exist_ok=True)
        Path(out_json).write_text(json.dumps(payload, indent=2, sort_keys=True))
    return payload


def _fetch_schedule_payload(requests: Any, target_date: str) -> dict[str, Any]:
    params = {
        "sportId": "1",
        "date": target_date,
        "hydrate": "probablePitcher,venue",
    }
    url = f"https://statsapi.mlb.com/api/v1/schedule?{urlencode(params)}"
    response = requests.get(url, timeout=30)
    response.raise_for_status()
    return response.json()


def _slate_is_complete(payload: dict[str, Any]) -> bool:
    games = [game for date_block in payload.get("dates", []) for game in date_block.get("games", [])]
    if not games:
        return False
    return all(game.get("status", {}).get("detailedState", "") in FINAL_STATES for game in games)


def load_schedule_json(path: str) -> dict[str, Any]:
    return json.loads(Path(path).read_text())


def schedule_payload_to_games(payload: dict[str, Any]) -> list[dict[str, object]]:
    games = []
    for date_block in payload.get("dates", []):
        game_date = date_block.get("date", "")
        for game in date_block.get("games", []):
            away = game.get("teams", {}).get("away", {})
            home = game.get("teams", {}).get("home", {})
            venue = game.get("venue", {})
            away_pitcher = away.get("probablePitcher", {})
            home_pitcher = home.get("probablePitcher", {})
            games.append({
                "date": game_date,
                "game_id": game.get("gamePk", ""),
                "away_team": _team_code(away.get("team", {}).get("name", "")),
                "home_team": _team_code(home.get("team", {}).get("name", "")),
                "away_team_name": away.get("team", {}).get("name", ""),
                "home_team_name": home.get("team", {}).get("name", ""),
                "away_sp_name": away_pitcher.get("fullName", ""),
                "home_sp_name": home_pitcher.get("fullName", ""),
                "away_sp_id": away_pitcher.get("id", ""),
                "home_sp_id": home_pitcher.get("id", ""),
                "venue_name": venue.get("name", ""),
                "commence_time": game.get("gameDate", ""),
            })
    return games


def _team_code(name: str) -> str:
    return MLB_TEAM_CODES.get(name, name)
