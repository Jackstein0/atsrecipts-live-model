from __future__ import annotations

from datetime import datetime
from math import cos, radians
from pathlib import Path
from zoneinfo import ZoneInfo

from .features import write_csv
from .schedule import fetch_mlb_schedule, load_schedule_json, schedule_payload_to_games


BALLPARK_WEATHER = {
    "ARI": (33.4455, -112.0667, True),
    "ATH": (38.5805, -121.5137, False),
    "ATL": (33.8907, -84.4677, False),
    "BAL": (39.2839, -76.6217, False),
    "BOS": (42.3467, -71.0972, False),
    "CHC": (41.9484, -87.6553, False),
    "CHW": (41.8300, -87.6339, False),
    "CIN": (39.0974, -84.5066, False),
    "CLE": (41.4962, -81.6852, False),
    "COL": (39.7561, -104.9942, False),
    "DET": (42.3390, -83.0485, False),
    "HOU": (29.7573, -95.3555, True),
    "KCR": (39.0517, -94.4803, False),
    "LAA": (33.8003, -117.8827, False),
    "LAD": (34.0739, -118.2400, False),
    "MIA": (25.7781, -80.2197, True),
    "MIL": (43.0280, -87.9712, True),
    "MIN": (44.9817, -93.2776, False),
    "NYM": (40.7571, -73.8458, False),
    "NYY": (40.8296, -73.9262, False),
    "PHI": (39.9061, -75.1665, False),
    "PIT": (40.4469, -80.0057, False),
    "SDP": (32.7073, -117.1566, False),
    "SEA": (47.5914, -122.3325, True),
    "SFG": (37.7786, -122.3893, False),
    "STL": (38.6226, -90.1928, False),
    "TBR": (27.7682, -82.6534, True),
    "TEX": (32.7473, -97.0842, True),
    "TOR": (43.6414, -79.3894, True),
    "WSN": (38.8730, -77.0074, False),
}


# Approximate compass bearing from home plate toward center field. It lets us
# convert weather-station wind direction into a runs-relevant out/in component.
CENTER_FIELD_BEARING = {
    "ARI": 20,
    "ATH": 45,
    "ATL": 160,
    "BAL": 30,
    "BOS": 45,
    "CHC": 40,
    "CHW": 130,
    "CIN": 120,
    "CLE": 10,
    "COL": 10,
    "DET": 155,
    "HOU": 25,
    "KCR": 45,
    "LAA": 45,
    "LAD": 40,
    "MIA": 70,
    "MIL": 140,
    "MIN": 95,
    "NYM": 10,
    "NYY": 75,
    "PHI": 95,
    "PIT": 30,
    "SDP": 20,
    "SEA": 65,
    "SFG": 90,
    "STL": 90,
    "TBR": 45,
    "TEX": 40,
    "TOR": 25,
    "WSN": 15,
}


def update_weather_metrics(
    out: str = "data/source/weather_metrics.csv",
    game_date: str | None = None,
    schedule_json: str | None = None,
    raw_schedule_json: str | None = "data/raw/today_schedule.json",
    raw_weather_dir: str = "data/raw/weather",
) -> int:
    payload = load_schedule_json(schedule_json) if schedule_json else fetch_mlb_schedule(game_date, raw_schedule_json)
    games = schedule_payload_to_games(payload)
    rows = []
    Path(raw_weather_dir).mkdir(parents=True, exist_ok=True)
    for game in games:
        home = str(game.get("home_team", ""))
        lat_lon_roof = BALLPARK_WEATHER.get(home)
        if not lat_lon_roof:
            rows.append(_fallback_weather(game))
            continue
        lat, lon, roof = lat_lon_roof
        try:
            weather = _fetch_open_meteo(lat, lon, str(game.get("commence_time", "")))
        except Exception:
            weather = None
        if weather:
            wind_out = 0 if roof else _wind_out_component(home, weather["wind_mph"], weather["wind_dir_degrees"])
            rows.append({
                "game_id": game.get("game_id", ""),
                "temp_f": weather["temp_f"],
                "wind_out_mph": wind_out,
                "wind_mph": weather["wind_mph"],
                "wind_dir_degrees": weather["wind_dir_degrees"],
                "roof": "yes" if roof else "no",
            })
        else:
            rows.append(_fallback_weather(game))
    write_csv(out, rows, ["game_id", "temp_f", "wind_out_mph", "wind_mph", "wind_dir_degrees", "roof"])
    return len(rows)


def _fetch_open_meteo(lat: float, lon: float, commence_time: str) -> dict[str, float] | None:
    import requests

    game_hour = _game_hour(commence_time)
    url = (
        "https://api.open-meteo.com/v1/forecast"
        f"?latitude={lat}&longitude={lon}"
        "&hourly=temperature_2m,wind_speed_10m,wind_direction_10m"
        "&temperature_unit=fahrenheit&wind_speed_unit=mph&forecast_days=3&timezone=UTC"
    )
    response = requests.get(url, timeout=5)
    response.raise_for_status()
    hourly = response.json().get("hourly", {})
    times = hourly.get("time", [])
    temps = hourly.get("temperature_2m", [])
    winds = hourly.get("wind_speed_10m", [])
    directions = hourly.get("wind_direction_10m", [])
    if not times:
        return None
    index = _nearest_hour_index(times, game_hour)
    return {
        "temp_f": round(float(temps[index]), 1),
        "wind_mph": round(float(winds[index]), 1),
        "wind_dir_degrees": round(float(directions[index]), 0) if directions else 0,
    }


def _game_hour(value: str) -> datetime:
    if not value:
        return datetime.now(tz=ZoneInfo("UTC"))
    return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(ZoneInfo("UTC")).replace(minute=0, second=0, microsecond=0)


def _nearest_hour_index(times: list[str], target: datetime) -> int:
    parsed = [datetime.fromisoformat(value).replace(tzinfo=ZoneInfo("UTC")) for value in times]
    return min(range(len(parsed)), key=lambda index: abs((parsed[index] - target).total_seconds()))


def _wind_out_component(team: str, wind_mph: float, wind_from_degrees: float) -> float:
    wind_to_degrees = (wind_from_degrees + 180) % 360
    out_degrees = CENTER_FIELD_BEARING.get(team, 45)
    diff = abs((wind_to_degrees - out_degrees + 180) % 360 - 180)
    return round(wind_mph * cos(radians(diff)), 1)


def _fallback_weather(game: dict[str, object]) -> dict[str, object]:
    return {"game_id": game.get("game_id", ""), "temp_f": "70", "wind_out_mph": "0", "wind_mph": "0", "wind_dir_degrees": "0", "roof": "unknown"}
