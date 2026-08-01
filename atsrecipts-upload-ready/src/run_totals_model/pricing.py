from __future__ import annotations

from math import erf, sqrt

from .model import TotalsModel


def american_to_decimal(odds: float) -> float:
    if odds > 0:
        return 1 + odds / 100
    return 1 + 100 / abs(odds)


def american_to_implied_probability(odds: float) -> float:
    if odds > 0:
        return 100 / (odds + 100)
    return abs(odds) / (abs(odds) + 100)


def normal_cdf(value: float, mean: float, std: float) -> float:
    std = max(std, 0.25)
    z = (value - mean) / (std * sqrt(2))
    return 0.5 * (1 + erf(z))


def price_totals(model: TotalsModel, board: list[dict[str, str]]) -> list[dict[str, object]]:
    if not board:
        return []
    required = {"market_total", "over_odds", "under_odds"}
    present = set(board[0].keys()) if board else set()
    missing = required - present
    if missing:
        raise ValueError(f"Board is missing required columns: {sorted(missing)}")

    model_totals = model.predict(board)
    priced = []
    for row, model_total in zip(board, model_totals):
        market_total = float(row["market_total"])
        over_odds = float(row["over_odds"])
        under_odds = float(row["under_odds"])
        under_probability = normal_cdf(market_total, float(model_total), model.residual_std)
        over_probability = 1 - under_probability
        over_ev = over_probability * american_to_decimal(over_odds) - 1
        under_ev = under_probability * american_to_decimal(under_odds) - 1
        best_side = "over" if over_ev >= under_ev else "under"
        best_ev = max(over_ev, under_ev)
        priced.append({
            **row,
            "model_total": float(model_total),
            "under_probability": under_probability,
            "over_probability": over_probability,
            "market_over_probability": american_to_implied_probability(over_odds),
            "market_under_probability": american_to_implied_probability(under_odds),
            "over_ev": over_ev,
            "under_ev": under_ev,
            "best_side": best_side,
            "best_ev": best_ev,
            "edge_label": edge_label(best_ev),
        })
    return sorted(priced, key=lambda row: float(row["best_ev"]), reverse=True)


def edge_label(best_ev: float) -> str:
    if best_ev >= 0.10:
        return "watch"
    if best_ev >= 0.04:
        return "lean"
    return "pass"
