from __future__ import annotations

from pathlib import Path

from .features import load_csv, write_csv
from .odds import MLB_TEAM_CODES


TEAM_ALIASES = {
    **MLB_TEAM_CODES,
    "AZ": "ARI",
    "ARI": "ARI",
    "ATH": "ATH",
    "ATL": "ATL",
    "BAL": "BAL",
    "BOS": "BOS",
    "CHC": "CHC",
    "CHW": "CHW",
    "CWS": "CHW",
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
}


def import_fangraphs_exports(
    team_batting: str = "data/fangraphs/team_batting.csv",
    starters: str = "data/fangraphs/starters.csv",
    bullpen: str = "data/fangraphs/bullpen.csv",
    team_metrics_out: str = "data/source/team_metrics.csv",
    starter_metrics_out: str = "data/source/starter_metrics.csv",
    bullpen_metrics_out: str = "data/source/bullpen_metrics.csv",
) -> dict[str, int]:
    counts = {"team_metrics": 0, "starter_metrics": 0, "bullpen_metrics": 0}
    if Path(team_batting).exists():
        rows = _team_batting_rows(load_csv(team_batting))
        if rows:
            write_csv(team_metrics_out, rows, ["team", "wrc_plus"])
            counts["team_metrics"] = len(rows)
    if Path(starters).exists():
        rows = _starter_rows(load_csv(starters))
        if rows:
            write_csv(starter_metrics_out, rows, ["mlbam_id", "pitcher_name", "xfip"])
            counts["starter_metrics"] = len(rows)
    if Path(bullpen).exists():
        rows = _bullpen_rows(load_csv(bullpen))
        if rows:
            write_csv(bullpen_metrics_out, rows, ["team", "bullpen_xfip"])
            counts["bullpen_metrics"] = len(rows)
    return counts


def write_fangraphs_templates(folder: str = "data/fangraphs") -> None:
    Path(folder).mkdir(parents=True, exist_ok=True)
    write_csv(f"{folder}/team_batting.csv", [], ["Team", "wRC+"])
    write_csv(f"{folder}/starters.csv", [], ["Name", "MLBAMID", "xFIP"])
    write_csv(f"{folder}/bullpen.csv", [], ["Team", "xFIP"])


def _team_batting_rows(rows: list[dict[str, str]]) -> list[dict[str, object]]:
    output = []
    for row in rows:
        team = _team_code(_first(row, "Team", "team", "Tm"))
        wrc_plus = _first(row, "wRC+", "wRC_plus", "wrc_plus", "WRC+")
        if team and wrc_plus:
            output.append({"team": team, "wrc_plus": _number(wrc_plus)})
    return output


def _starter_rows(rows: list[dict[str, str]]) -> list[dict[str, object]]:
    output = []
    for row in rows:
        name = _first(row, "Name", "Player", "player_name", "pitcher_name")
        mlbam_id = _first(row, "MLBAMID", "MLBAM Id", "mlbam_id", "mlb_id", "playerid")
        xfip = _first(row, "xFIP", "xfip", "sp_xfip")
        if name and xfip:
            output.append({"mlbam_id": mlbam_id, "pitcher_name": name, "xfip": _number(xfip)})
    return output


def _bullpen_rows(rows: list[dict[str, str]]) -> list[dict[str, object]]:
    output = []
    for row in rows:
        team = _team_code(_first(row, "Team", "team", "Tm"))
        xfip = _first(row, "xFIP", "xfip", "bullpen_xfip")
        if team and xfip:
            output.append({"team": team, "bullpen_xfip": _number(xfip)})
    return output


def _first(row: dict[str, str], *keys: str) -> str:
    lowered = {key.lower().replace(" ", "_"): value for key, value in row.items()}
    for key in keys:
        value = row.get(key)
        if value not in (None, ""):
            return str(value).strip()
        value = lowered.get(key.lower().replace(" ", "_"))
        if value not in (None, ""):
            return str(value).strip()
    return ""


def _team_code(value: str) -> str:
    cleaned = value.strip()
    return TEAM_ALIASES.get(cleaned, TEAM_ALIASES.get(cleaned.upper(), cleaned.upper()))


def _number(value: str) -> float:
    return float(str(value).replace("%", "").replace(",", "").strip())
