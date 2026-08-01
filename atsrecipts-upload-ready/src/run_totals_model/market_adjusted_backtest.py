from __future__ import annotations

from pathlib import Path

from .backtest import BacktestSummary, _bet_columns, _grade_bet, _summary_row, summarize_bets
from .features import load_games, write_csv
from .market_adjusted import train_market_adjusted_model
from .pricing import price_totals


def run_market_adjusted_walk_forward_backtest(
    input_path: str,
    bets_out: str,
    summary_out: str,
    min_train_games: int = 200,
    ev_threshold: float = 0.03,
    ridge_alpha: float = 12.0,
) -> BacktestSummary:
    rows = sorted(load_games(input_path), key=lambda row: row.get("date", ""))
    if len(rows) <= min_train_games:
        raise ValueError(f"Need more than {min_train_games} rows for this backtest.")

    bet_rows = []
    for index in range(min_train_games, len(rows)):
        train_rows = rows[:index]
        test_row = rows[index]
        model = train_market_adjusted_model(train_rows, ridge_alpha=ridge_alpha)
        priced = price_totals(model, [test_row])[0]
        if float(priced["best_ev"]) < ev_threshold:
            continue
        bet_rows.append(_grade_bet(priced))

    summary = summarize_bets(len(rows) - min_train_games, bet_rows)
    summary.note = (
        "Model B uses the sportsbook total as a baseline and learns residual adjustments. "
        "Historical market totals in the current scaffold may be proxies unless you replace "
        "historical_games.csv with real pregame sportsbook lines."
    )
    write_csv(bets_out, bet_rows, _bet_columns())
    write_csv(summary_out, [_summary_row(summary)], list(_summary_row(summary).keys()))
    return summary


def write_market_adjusted_text_report(summary: BacktestSummary, path: str) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(
        "\n".join([
            "MLB Run Totals Backtest - Model B",
            "=================================",
            "",
            "Approach: market-adjusted residual model",
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
