from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .features import load_games, write_csv
from .model import train_totals_model
from .pricing import american_to_decimal, price_totals


@dataclass
class BacktestSummary:
    games_tested: int
    bets: int
    wins: int
    losses: int
    pushes: int
    profit_units: float
    roi: float
    avg_ev: float
    note: str


def run_walk_forward_backtest(
    input_path: str,
    bets_out: str,
    summary_out: str,
    min_train_games: int = 200,
    ev_threshold: float = 0.03,
    ridge_alpha: float = 10.0,
) -> BacktestSummary:
    rows = sorted(load_games(input_path), key=lambda row: row.get("date", ""))
    if len(rows) <= min_train_games:
        raise ValueError(f"Need more than {min_train_games} rows for this backtest.")

    bet_rows = []
    for index in range(min_train_games, len(rows)):
        train_rows = rows[:index]
        test_row = rows[index]
        model = train_totals_model(train_rows, ridge_alpha=ridge_alpha)
        priced = price_totals(model, [test_row])[0]
        if float(priced["best_ev"]) < ev_threshold:
            continue
        bet_rows.append(_grade_bet(priced))

    summary = summarize_bets(len(rows) - min_train_games, bet_rows)
    write_csv(bets_out, bet_rows, _bet_columns())
    write_csv(summary_out, [_summary_row(summary)], list(_summary_row(summary).keys()))
    return summary


def summarize_bets(games_tested: int, bet_rows: list[dict[str, object]]) -> BacktestSummary:
    bets = len(bet_rows)
    wins = sum(1 for row in bet_rows if row["result"] == "win")
    losses = sum(1 for row in bet_rows if row["result"] == "loss")
    pushes = sum(1 for row in bet_rows if row["result"] == "push")
    profit = sum(float(row["profit_units"]) for row in bet_rows)
    roi = profit / bets if bets else 0.0
    avg_ev = sum(float(row["best_ev"]) for row in bet_rows) / bets if bets else 0.0
    return BacktestSummary(
        games_tested=games_tested,
        bets=bets,
        wins=wins,
        losses=losses,
        pushes=pushes,
        profit_units=profit,
        roi=roi,
        avg_ev=avg_ev,
        note=(
            "Historical market totals in the current scaffold may be proxies unless "
            "you replace historical_games.csv with real pregame sportsbook lines."
        ),
    )


def _grade_bet(row: dict[str, object]) -> dict[str, object]:
    total_runs = float(row["total_runs"])
    market_total = float(row["market_total"])
    side = str(row["best_side"])
    odds = float(row["over_odds"] if side == "over" else row["under_odds"])
    if total_runs == market_total:
        result = "push"
        profit = 0.0
    elif side == "over" and total_runs > market_total:
        result = "win"
        profit = american_to_decimal(odds) - 1
    elif side == "under" and total_runs < market_total:
        result = "win"
        profit = american_to_decimal(odds) - 1
    else:
        result = "loss"
        profit = -1.0

    return {
        "date": row.get("date", ""),
        "away_team": row.get("away_team", ""),
        "home_team": row.get("home_team", ""),
        "market_total": row.get("market_total", ""),
        "total_runs": total_runs,
        "model_total": row.get("model_total", ""),
        "bet_side": side,
        "odds": int(odds),
        "best_ev": row.get("best_ev", ""),
        "over_probability": row.get("over_probability", ""),
        "under_probability": row.get("under_probability", ""),
        "result": result,
        "profit_units": round(profit, 4),
    }


def _summary_row(summary: BacktestSummary) -> dict[str, object]:
    return {
        "games_tested": summary.games_tested,
        "bets": summary.bets,
        "wins": summary.wins,
        "losses": summary.losses,
        "pushes": summary.pushes,
        "profit_units": round(summary.profit_units, 4),
        "roi": round(summary.roi, 4),
        "avg_ev": round(summary.avg_ev, 4),
        "note": summary.note,
    }


def write_text_report(summary: BacktestSummary, path: str) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(
        "\n".join([
            "MLB Run Totals Backtest",
            "=======================",
            "",
            f"Games tested: {summary.games_tested}",
            f"Bets placed: {summary.bets}",
            f"Wins: {summary.wins}",
            f"Losses: {summary.losses}",
            f"Pushes: {summary.pushes}",
            f"Profit: {summary.profit_units:.2f} units",
            f"ROI: {summary.roi:.2%}",
            f"Average model EV: {summary.avg_ev:.2%}",
            "",
            "Important:",
            summary.note,
            "",
        ])
    )


def _bet_columns() -> list[str]:
    return [
        "date",
        "away_team",
        "home_team",
        "market_total",
        "total_runs",
        "model_total",
        "bet_side",
        "odds",
        "best_ev",
        "over_probability",
        "under_probability",
        "result",
        "profit_units",
    ]

