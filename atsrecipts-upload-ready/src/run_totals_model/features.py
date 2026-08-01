from __future__ import annotations

from dataclasses import dataclass
import csv
from pathlib import Path
from typing import Iterable

OUTCOME_COLUMNS = {
    "away_runs",
    "home_runs",
    "total_runs",
    "over_result",
    "under_result",
}

MARKET_COLUMNS = {
    "market_total",
    "over_odds",
    "under_odds",
}

IDENTITY_COLUMNS = {
    "date",
    "away_team",
    "home_team",
    "game_id",
}


@dataclass(frozen=True)
class FeatureFrame:
    rows: list[dict[str, str]]
    feature_columns: list[str]
    matrix: list[list[float]]


def load_csv(path: str) -> list[dict[str, str]]:
    with open(path, newline="") as handle:
        return list(csv.DictReader(handle))


def load_games(path: str) -> list[dict[str, str]]:
    games = load_csv(path)
    for row in games:
        if not row.get("total_runs") and row.get("away_runs") and row.get("home_runs"):
            row["total_runs"] = str(float(row["away_runs"]) + float(row["home_runs"]))
    return games


def write_csv(path: str, rows: list[dict[str, object]], columns: list[str]) -> None:
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def _to_float(value: object) -> float | None:
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def infer_feature_columns(rows: list[dict[str, str]], extra_exclude: Iterable[str] = ()) -> list[str]:
    if not rows:
        return []
    excluded = OUTCOME_COLUMNS | MARKET_COLUMNS | IDENTITY_COLUMNS | set(extra_exclude)
    columns = rows[0].keys()
    feature_columns = []
    for column in columns:
        if column in excluded:
            continue
        values = [_to_float(row.get(column)) for row in rows]
        if any(value is not None for value in values):
            feature_columns.append(column)
    return feature_columns


def build_feature_frame(rows: list[dict[str, str]], feature_columns: list[str] | None = None) -> FeatureFrame:
    if feature_columns is None:
        feature_columns = infer_feature_columns(rows)
    present = set(rows[0].keys()) if rows else set()
    missing = [column for column in feature_columns if column not in present]
    if missing:
        raise ValueError(f"Missing feature columns: {missing}")

    medians: dict[str, float] = {}
    for column in feature_columns:
        values = sorted(value for row in rows if (value := _to_float(row.get(column))) is not None)
        medians[column] = values[len(values) // 2] if values else 0.0

    matrix = []
    for row in rows:
        matrix.append([
            _to_float(row.get(column)) if _to_float(row.get(column)) is not None else medians[column]
            for column in feature_columns
        ])
    return FeatureFrame(rows, feature_columns, matrix)
