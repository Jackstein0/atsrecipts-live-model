from __future__ import annotations

from dataclasses import asdict, dataclass
import json
from pathlib import Path

import numpy as np

from .features import _to_float


ENGINEERED_FEATURES = [
    "offense_stack",
    "offense_gap",
    "starter_pressure",
    "starter_gap",
    "bullpen_pressure",
    "bullpen_gap",
    "park_boost",
    "heat_boost",
    "wind_out_mph",
    "weather_boost",
]


@dataclass
class MarketAdjustedTotalsModel:
    feature_columns: list[str]
    coefficients: list[float]
    intercept: float
    feature_means: dict[str, float]
    feature_stds: dict[str, float]
    residual_std: float
    ridge_alpha: float
    description: str

    def predict(self, rows: list[dict[str, str]]) -> np.ndarray:
        if not rows:
            return np.array([])
        x = np.array([engineer_features(row) for row in rows], dtype=float)
        means = np.array([self.feature_means[column] for column in self.feature_columns])
        stds = np.array([self.feature_stds[column] for column in self.feature_columns])
        x_scaled = (x - means) / stds
        market_totals = np.array([float(row["market_total"]) for row in rows], dtype=float)
        residual_adjustment = self.intercept + x_scaled @ np.array(self.coefficients)
        return market_totals + residual_adjustment

    def save(self, path: str | Path) -> None:
        target = Path(path)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(asdict(self), indent=2, sort_keys=True))

    @classmethod
    def load(cls, path: str | Path) -> "MarketAdjustedTotalsModel":
        return cls(**json.loads(Path(path).read_text()))


def train_market_adjusted_model(rows: list[dict[str, str]], ridge_alpha: float = 12.0) -> MarketAdjustedTotalsModel:
    if not rows or "total_runs" not in rows[0]:
        raise ValueError("Training data must include total_runs or away_runs/home_runs.")
    if "market_total" not in rows[0]:
        raise ValueError("Market-adjusted training data must include market_total.")

    x = np.array([engineer_features(row) for row in rows], dtype=float)
    y = np.array([float(row["total_runs"]) - float(row["market_total"]) for row in rows], dtype=float)

    means = x.mean(axis=0)
    stds = x.std(axis=0)
    stds[stds == 0] = 1.0
    x_scaled = (x - means) / stds
    design = np.column_stack([np.ones(len(x_scaled)), x_scaled])

    penalty = np.eye(design.shape[1]) * ridge_alpha
    penalty[0, 0] = 0.0
    params = np.linalg.solve(design.T @ design + penalty, design.T @ y)

    fitted_adjustments = design @ params
    fitted_totals = np.array([float(row["market_total"]) for row in rows], dtype=float) + fitted_adjustments
    actual_totals = np.array([float(row["total_runs"]) for row in rows], dtype=float)
    dof = max(len(actual_totals) - design.shape[1], 1)
    residual_std = float(np.sqrt(np.sum((actual_totals - fitted_totals) ** 2) / dof))

    return MarketAdjustedTotalsModel(
        feature_columns=ENGINEERED_FEATURES,
        coefficients=params[1:].tolist(),
        intercept=float(params[0]),
        feature_means=dict(zip(ENGINEERED_FEATURES, means.tolist())),
        feature_stds=dict(zip(ENGINEERED_FEATURES, stds.tolist())),
        residual_std=residual_std,
        ridge_alpha=ridge_alpha,
        description=(
            "Model B: market-adjusted totals model. Uses sportsbook total as the baseline "
            "and learns baseball-condition residuals from offense, starters, bullpen, park, and weather."
        ),
    )


def engineer_features(row: dict[str, str]) -> list[float]:
    home_wrc = _number(row, "home_wrc_plus", 100.0)
    away_wrc = _number(row, "away_wrc_plus", 100.0)
    home_sp = _number(row, "home_sp_xfip", 4.2)
    away_sp = _number(row, "away_sp_xfip", 4.2)
    home_pen = _number(row, "home_bullpen_xfip", 4.2)
    away_pen = _number(row, "away_bullpen_xfip", 4.2)
    park = _number(row, "park_factor", 100.0)
    temp = _number(row, "temp_f", 70.0)
    wind = _number(row, "wind_out_mph", 0.0)

    offense_stack = (home_wrc + away_wrc) - 200.0
    offense_gap = home_wrc - away_wrc
    starter_pressure = (home_sp + away_sp) - 8.4
    starter_gap = home_sp - away_sp
    bullpen_pressure = (home_pen + away_pen) - 8.4
    bullpen_gap = home_pen - away_pen
    park_boost = park - 100.0
    heat_boost = (temp - 70.0) / 10.0
    weather_boost = heat_boost + (wind * 0.15)

    return [
        offense_stack,
        offense_gap,
        starter_pressure,
        starter_gap,
        bullpen_pressure,
        bullpen_gap,
        park_boost,
        heat_boost,
        wind,
        weather_boost,
    ]


def _number(row: dict[str, str], column: str, fallback: float) -> float:
    value = _to_float(row.get(column))
    return fallback if value is None else value
