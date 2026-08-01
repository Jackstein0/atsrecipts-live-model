from __future__ import annotations

from dataclasses import asdict, dataclass
import json
from pathlib import Path

import numpy as np

from .features import build_feature_frame


@dataclass
class TotalsModel:
    feature_columns: list[str]
    coefficients: list[float]
    intercept: float
    feature_means: dict[str, float]
    feature_stds: dict[str, float]
    residual_std: float
    ridge_alpha: float

    def predict(self, rows: list[dict[str, str]]) -> np.ndarray:
        feature_frame = build_feature_frame(rows, self.feature_columns)
        x = np.array(feature_frame.matrix, dtype=float)
        means = np.array([self.feature_means[column] for column in self.feature_columns])
        stds = np.array([self.feature_stds[column] for column in self.feature_columns])
        x_scaled = (x - means) / stds
        return self.intercept + x_scaled @ np.array(self.coefficients)

    def save(self, path: str | Path) -> None:
        target = Path(path)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(asdict(self), indent=2, sort_keys=True))

    @classmethod
    def load(cls, path: str | Path) -> "TotalsModel":
        return cls(**json.loads(Path(path).read_text()))


def train_totals_model(rows: list[dict[str, str]], ridge_alpha: float = 10.0) -> TotalsModel:
    if not rows or "total_runs" not in rows[0]:
        raise ValueError("Training data must include total_runs or away_runs/home_runs.")

    feature_frame = build_feature_frame(rows)
    feature_columns = feature_frame.feature_columns
    if not feature_columns:
        raise ValueError("No numeric feature columns found.")

    x = np.array(feature_frame.matrix, dtype=float)
    y = np.array([float(row["total_runs"]) for row in rows], dtype=float)

    means = x.mean(axis=0)
    stds = x.std(axis=0)
    stds[stds == 0] = 1.0
    x_scaled = (x - means) / stds
    design = np.column_stack([np.ones(len(x_scaled)), x_scaled])

    penalty = np.eye(design.shape[1]) * ridge_alpha
    penalty[0, 0] = 0.0
    params = np.linalg.solve(design.T @ design + penalty, design.T @ y)

    fitted = design @ params
    dof = max(len(y) - design.shape[1], 1)
    residual_std = float(np.sqrt(np.sum((y - fitted) ** 2) / dof))

    return TotalsModel(
        feature_columns=feature_columns,
        coefficients=params[1:].tolist(),
        intercept=float(params[0]),
        feature_means=dict(zip(feature_columns, means.tolist())),
        feature_stds=dict(zip(feature_columns, stds.tolist())),
        residual_std=residual_std,
        ridge_alpha=ridge_alpha,
    )
