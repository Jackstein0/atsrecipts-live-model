from __future__ import annotations

from datetime import datetime, timezone
import json
import os
from pathlib import Path
from collections import Counter
from statistics import median
from typing import Any
from urllib.parse import urlencode
from zoneinfo import ZoneInfo


MLB_TEAM_CODES = {
    "Arizona Diamondbacks": "ARI",
    "Athletics": "ATH",
    "Atlanta Braves": "ATL",
    "Baltimore Orioles": "BAL",
    "Boston Red Sox": "BOS",
    "Chicago Cubs": "CHC",
    "Chicago White Sox": "CHW",
    "Cincinnati Reds": "CIN",
    "Cleveland Guardians": "CLE",
    "Colorado Rockies": "COL",
    "Detroit Tigers": "DET",
    "Houston Astros": "HOU",
    "Kansas City Royals": "KCR",
    "Los Angeles Angels": "LAA",
    "Los Angeles Dodgers": "LAD",
    "Miami Marlins": "MIA",
    "Milwaukee Brewers": "MIL",
    "Minnesota Twins": "MIN",
    "New York Mets": "NYM",
    "New York Yankees": "NYY",
    "Philadelphia Phillies": "PHI",
    "Pittsburgh Pirates": "PIT",
    "San Diego Padres": "SDP",
    "San Francisco Giants": "SFG",
    "Seattle Mariners": "SEA",
    "St Louis Cardinals": "STL",
    "St. Louis Cardinals": "STL",
    "Tampa Bay Rays": "TBR",
    "Texas Rangers": "TEX",
    "Toronto Blue Jays": "TOR",
    "Washington Nationals": "WSN",
}


def fetch_the_odds_api_totals(
    api_key: str | None = None,
    regions: str = "us",
    bookmakers: str | None = None,
    out_json: str | None = None,
) -> list[dict[str, Any]]:
    import requests

    key = api_key or os.environ.get("THE_ODDS_API_KEY")
    if not key:
        raise ValueError("Missing API key. Set THE_ODDS_API_KEY or pass --api-key.")

    params = {
        "apiKey": key,
        "markets": "totals",
        "oddsFormat": "american",
        "dateFormat": "iso",
    }
    if bookmakers:
        params["bookmakers"] = bookmakers
    else:
        params["regions"] = regions

    url = f"https://api.the-odds-api.com/v4/sports/baseball_mlb/odds/?{urlencode(params)}"
    response = requests.get(url, timeout=30)
    response.raise_for_status()
    payload = response.json()
    if out_json:
        Path(out_json).parent.mkdir(parents=True, exist_ok=True)
        Path(out_json).write_text(json.dumps(payload, indent=2, sort_keys=True))
    return payload


def totals_payload_to_board(
    payload: list[dict[str, Any]],
    bookmaker: str | None = None,
    aggregate: str = "median",
    pregame_only: bool = True,
) -> list[dict[str, object]]:
    rows = []
    now = datetime.now(timezone.utc)
    for event in payload:
        commence_time = event.get("commence_time", "")
        if pregame_only and _has_started(commence_time, now):
            continue
        offers = _extract_total_offers(event, bookmaker)
        if not offers:
            continue
        offer = _aggregate_offers(offers, aggregate)
        rows.append({
            "date": _date_part(event.get("commence_time", "")),
            "away_team": _team_code(event.get("away_team", "")),
            "home_team": _team_code(event.get("home_team", "")),
            "market_total": offer["market_total"],
            "over_odds": offer["over_odds"],
            "under_odds": offer["under_odds"],
            "sportsbook": offer["sportsbook"],
            "commence_time": commence_time,
        })
    return rows


def merge_odds_with_features(
    odds_rows: list[dict[str, object]],
    feature_rows: list[dict[str, str]],
) -> list[dict[str, object]]:
    features_by_key = {
        _game_key(row): row
        for row in feature_rows
    }
    merged = []
    for odds_row in odds_rows:
        feature_row = features_by_key.get(_game_key(odds_row))
        if feature_row:
            merged.append({**feature_row, **odds_row})
    return merged


def odds_columns(rows: list[dict[str, object]]) -> list[str]:
    preferred = [
        "date",
        "away_team",
        "home_team",
        "market_total",
        "over_odds",
        "under_odds",
        "sportsbook",
        "commence_time",
    ]
    if not rows:
        return preferred
    extras = [column for column in rows[0].keys() if column not in preferred]
    return preferred + extras


def _extract_total_offers(event: dict[str, Any], bookmaker: str | None) -> list[dict[str, object]]:
    offers = []
    for book in event.get("bookmakers", []):
        if bookmaker and book.get("key") != bookmaker:
            continue
        for market in book.get("markets", []):
            if market.get("key") != "totals":
                continue
            over = _find_outcome(market.get("outcomes", []), "Over")
            under = _find_outcome(market.get("outcomes", []), "Under")
            if over and under and over.get("point") == under.get("point"):
                offers.append({
                    "sportsbook": book.get("key", ""),
                    "market_total": float(over["point"]),
                    "over_odds": int(over["price"]),
                    "under_odds": int(under["price"]),
                })
    return offers


def _aggregate_offers(offers: list[dict[str, object]], aggregate: str) -> dict[str, object]:
    if aggregate == "first" or len(offers) == 1:
        return offers[0]
    if aggregate != "median":
        raise ValueError("aggregate must be 'median' or 'first'")
    main_total = Counter(float(offer["market_total"]) for offer in offers).most_common(1)[0][0]
    main_offers = [offer for offer in offers if float(offer["market_total"]) == main_total]
    # Do not median American odds: mixing + and - prices can create invalid
    # values near zero. Use the first available price at the consensus total.
    selected = main_offers[0]
    return {
        "sportsbook": selected.get("sportsbook", "consensus"),
        "market_total": main_total,
        "over_odds": selected["over_odds"],
        "under_odds": selected["under_odds"],
    }


def _find_outcome(outcomes: list[dict[str, Any]], name: str) -> dict[str, Any] | None:
    for outcome in outcomes:
        if outcome.get("name") == name:
            return outcome
    return None


def _team_code(name: str) -> str:
    return MLB_TEAM_CODES.get(name, name)


def _date_part(value: str) -> str:
    if not value:
        return ""
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(ZoneInfo("America/New_York")).date().isoformat()
    except ValueError:
        return value[:10]


def _has_started(value: str, now: datetime) -> bool:
    if not value:
        return False
    try:
        commence = datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(timezone.utc)
    except ValueError:
        return False
    return commence <= now


def _game_key(row: dict[str, object]) -> tuple[str, str, str]:
    return (str(row.get("date", "")), str(row.get("away_team", "")), str(row.get("home_team", "")))
