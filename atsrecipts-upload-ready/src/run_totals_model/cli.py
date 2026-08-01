from __future__ import annotations

import argparse
from pathlib import Path

from .backtest import run_walk_forward_backtest, write_text_report
from .daily_docs import archive_current_outputs, document_games
from .fangraphs_import import import_fangraphs_exports, write_fangraphs_templates
from .features import load_csv, load_games
from .features import write_csv
from .historical_odds import apply_historical_odds, fetch_historical_totals_for_training, normalize_historical_odds_csv, test_historical_access, write_historical_odds_template
from .market_adjusted import MarketAdjustedTotalsModel, train_market_adjusted_model
from .model import TotalsModel, train_totals_model
from .odds import fetch_the_odds_api_totals, merge_odds_with_features, odds_columns, totals_payload_to_board
from .pricing import price_totals
from .real_data import update_real_data
from .report import write_data_audit_html, write_today_html
from .status import print_status
from .today_features import FEATURE_COLUMNS, build_today_features
from .tracker import append_picks, grade_tracker, remove_picks_for_date, write_tracker_report
from .weather import update_weather_metrics


def train(args: argparse.Namespace) -> None:
    games = load_games(args.input)
    model = train_totals_model(games, ridge_alpha=args.ridge_alpha)
    model.save(args.model_out)
    print(f"saved model to {args.model_out}")
    print(f"features: {', '.join(model.feature_columns)}")
    print(f"residual_std: {model.residual_std:.3f}")


def train_market_adjusted(args: argparse.Namespace) -> None:
    games = load_games(args.input)
    model = train_market_adjusted_model(games, ridge_alpha=args.ridge_alpha)
    model.save(args.model_out)
    print(f"saved market-adjusted model to {args.model_out}")
    print(f"features: {', '.join(model.feature_columns)}")
    print(f"residual_std: {model.residual_std:.3f}")


def price(args: argparse.Namespace) -> None:
    model = TotalsModel.load(args.model)
    _price_with_model(model, args)


def price_market_adjusted(args: argparse.Namespace) -> None:
    model = MarketAdjustedTotalsModel.load(args.model)
    _price_with_model(model, args)


def _price_with_model(model: TotalsModel | MarketAdjustedTotalsModel, args: argparse.Namespace) -> None:
    board = load_csv(args.input)
    priced = price_totals(model, board)
    if args.preserve_existing and args.out:
        priced = _preserve_existing_priced_rows(priced, args.out)
    present = set(priced[0].keys()) if priced else set()
    columns = [
        column
        for column in [
            "date",
            "away_team",
            "home_team",
            "market_total",
            "model_total",
            "best_side",
            "edge_label",
            "best_ev",
            "over_probability",
            "under_probability",
            "over_ev",
            "under_ev",
        ]
        if column in present
    ]
    if columns:
        widths = {column: max(len(column), *(len(_format(row.get(column, ""))) for row in priced)) for column in columns}
        print(" ".join(column.ljust(widths[column]) for column in columns))
        for row in priced:
            print(" ".join(_format(row.get(column, "")).ljust(widths[column]) for column in columns))
    else:
        print("no pregame totals available to price")
    if args.out:
        output_columns = list(priced[0].keys()) if priced else [
            "date",
            "away_team",
            "home_team",
            "market_total",
            "model_total",
            "best_side",
            "edge_label",
            "best_ev",
        ]
        write_csv(args.out, priced, output_columns)
        print(f"\nsaved priced board to {args.out}")


def _preserve_existing_priced_rows(priced: list[dict[str, object]], out_path: str) -> list[dict[str, object]]:
    path = Path(out_path)
    existing = load_csv(str(path)) if path.exists() else []
    if not existing:
        return priced
    if not priced:
        return existing

    current_dates = {str(row.get("date", "")) for row in priced if row.get("date")}
    by_game = {_game_key(row): row for row in existing if str(row.get("date", "")) in current_dates}
    for row in priced:
        by_game[_game_key(row)] = row
    return sorted(
        by_game.values(),
        key=lambda row: (str(row.get("commence_time", "")), str(row.get("away_team", "")), str(row.get("home_team", ""))),
    )


def _game_key(row: dict[str, object]) -> tuple[str, str, str]:
    return (str(row.get("date", "")), str(row.get("away_team", "")), str(row.get("home_team", "")))


def _format(value: object) -> str:
    if isinstance(value, float):
        return f"{value:.3f}"
    return str(value)


def fetch(args: argparse.Namespace) -> None:
    from .scrape import fetch_url

    path = fetch_url(args.url, Path(args.out))
    print(f"cached {args.url} to {path}")


def odds_current(args: argparse.Namespace) -> None:
    try:
        payload = fetch_the_odds_api_totals(
            api_key=args.api_key,
            regions=args.regions,
            bookmakers=args.bookmakers,
            out_json=args.raw_json,
        )
    except Exception as error:
        raise SystemExit(f"Could not fetch odds. Check your internet connection and API key. Details: {error.__class__.__name__}") from error
    odds_rows = totals_payload_to_board(payload, bookmaker=args.bookmaker, aggregate=args.aggregate)
    rows = odds_rows
    if args.features:
        rows = merge_odds_with_features(odds_rows, load_csv(args.features))
        print(f"merged {len(rows)} odds rows with features from {args.features}")
    write_csv(args.out, rows, odds_columns(rows))
    print(f"saved {len(rows)} MLB totals rows to {args.out}")


def odds_from_json(args: argparse.Namespace) -> None:
    import json

    payload = json.loads(Path(args.input).read_text())
    odds_rows = totals_payload_to_board(payload, bookmaker=args.bookmaker, aggregate=args.aggregate)
    rows = odds_rows
    if args.features:
        rows = merge_odds_with_features(odds_rows, load_csv(args.features))
        print(f"merged {len(rows)} odds rows with features from {args.features}")
    write_csv(args.out, rows, odds_columns(rows))
    print(f"saved {len(rows)} MLB totals rows to {args.out}")


def features_today(args: argparse.Namespace) -> None:
    rows = build_today_features(
        game_date=args.date,
        out=args.out,
        team_metrics=args.team_metrics,
        starter_metrics=args.starter_metrics,
        bullpen_metrics=args.bullpen_metrics,
        park_metrics=args.park_metrics,
        weather_metrics=args.weather_metrics,
        schedule_json=args.schedule_json,
        raw_schedule_json=args.raw_schedule_json,
    )
    print(f"saved {len(rows)} feature rows to {args.out}")


def init_source_csvs(args: argparse.Namespace) -> None:
    _write_template_if_missing(args.team_metrics, ["team", "wrc_plus"])
    _write_template_if_missing(args.starter_metrics, ["mlbam_id", "pitcher_name", "xfip"])
    _write_template_if_missing(args.bullpen_metrics, ["team", "bullpen_xfip"])
    _write_template_if_missing(args.park_metrics, ["team", "park_factor"])
    _write_template_if_missing(args.weather_metrics, ["game_id", "temp_f", "wind_out_mph"])
    print("created source CSV templates")


def _write_template_if_missing(path: str, columns: list[str]) -> None:
    if Path(path).exists():
        print(f"kept existing {path}")
        return
    write_csv(path, [], columns)
    print(f"created {path}")


def status(args: argparse.Namespace) -> None:
    ready = print_status(args.root)
    if args.fail_if_missing and not ready:
        raise SystemExit(1)


def update_data(args: argparse.Namespace) -> None:
    update_real_data(
        game_date=args.date,
        lookback_days=args.lookback_days,
        team_metrics=args.team_metrics,
        starter_metrics=args.starter_metrics,
        bullpen_metrics=args.bullpen_metrics,
        park_metrics=args.park_metrics,
        weather_metrics=args.weather_metrics,
        historical_games=args.historical_games,
        raw_dir=args.raw_dir,
    )
    print("updated real MLB source data")


def fangraphs_templates(args: argparse.Namespace) -> None:
    write_fangraphs_templates(args.folder)
    print(f"created FanGraphs export templates in {args.folder}")


def fangraphs_import(args: argparse.Namespace) -> None:
    counts = import_fangraphs_exports(
        team_batting=args.team_batting,
        starters=args.starters,
        bullpen=args.bullpen,
        team_metrics_out=args.team_metrics_out,
        starter_metrics_out=args.starter_metrics_out,
        bullpen_metrics_out=args.bullpen_metrics_out,
    )
    print(
        "imported FanGraphs exports: "
        f"{counts['team_metrics']} team rows, "
        f"{counts['starter_metrics']} starter rows, "
        f"{counts['bullpen_metrics']} bullpen rows"
    )


def weather_update(args: argparse.Namespace) -> None:
    count = update_weather_metrics(
        out=args.out,
        game_date=args.date,
        schedule_json=args.schedule_json,
        raw_schedule_json=args.raw_schedule_json,
        raw_weather_dir=args.raw_weather_dir,
    )
    print(f"updated weather for {count} games")


def backtest(args: argparse.Namespace) -> None:
    summary = run_walk_forward_backtest(
        input_path=args.input,
        bets_out=args.bets_out,
        summary_out=args.summary_out,
        min_train_games=args.min_train_games,
        ev_threshold=args.ev_threshold,
        ridge_alpha=args.ridge_alpha,
    )
    write_text_report(summary, args.report_out)
    print(f"backtest complete: {summary.bets} bets, {summary.profit_units:.2f} units, ROI {summary.roi:.2%}")
    print(f"saved bets to {args.bets_out}")
    print(f"saved summary to {args.summary_out}")
    print(f"saved report to {args.report_out}")


def backtest_market_adjusted(args: argparse.Namespace) -> None:
    from .market_adjusted_backtest import run_market_adjusted_walk_forward_backtest, write_market_adjusted_text_report

    summary = run_market_adjusted_walk_forward_backtest(
        input_path=args.input,
        bets_out=args.bets_out,
        summary_out=args.summary_out,
        min_train_games=args.min_train_games,
        ev_threshold=args.ev_threshold,
        ridge_alpha=args.ridge_alpha,
    )
    write_market_adjusted_text_report(summary, args.report_out)
    print(f"Model B backtest complete: {summary.bets} bets, {summary.profit_units:.2f} units, ROI {summary.roi:.2%}")
    print(f"saved bets to {args.bets_out}")
    print(f"saved summary to {args.summary_out}")
    print(f"saved report to {args.report_out}")


def report_today(args: argparse.Namespace) -> None:
    write_today_html(args.results, args.out, args.backtest, args.tracker)
    print(f"saved report to {args.out}")


def report_data(args: argparse.Namespace) -> None:
    write_data_audit_html(args.root, args.out)
    print(f"saved data audit report to {args.out}")


def track_picks(args: argparse.Namespace) -> None:
    added, updated, total = append_picks(args.results, args.tracker, args.min_label)
    print(f"added {added} picks and refreshed {updated} open picks; {total} total tracked picks")


def grade_picks(args: argparse.Namespace) -> None:
    graded, summary = grade_tracker(args.tracker)
    write_tracker_report(args.tracker, args.report_out)
    print(f"graded {graded} completed picks")
    print(f"tracker summary: {summary}")
    print(f"saved tracker report to {args.report_out}")


def remove_tracked_date(args: argparse.Namespace) -> None:
    removed, remaining = remove_picks_for_date(args.tracker, args.date)
    write_tracker_report(args.tracker, args.report_out)
    print(f"removed {removed} tracked picks for {args.date}; {remaining} picks remain")


def document_games_cmd(args: argparse.Namespace) -> None:
    games, picks = document_games(args.date, args.out_csv, args.out_html, args.tracker)
    print(f"documented {games} games and {picks} tracked picks")
    print(f"saved CSV to {args.out_csv}")
    print(f"saved HTML to {args.out_html}")


def archive_outputs(args: argparse.Namespace) -> None:
    archived = archive_current_outputs(args.results, args.report)
    print(f"archived {len(archived)} files")
    for path in archived:
        print(path)


def historical_access(args: argparse.Namespace) -> None:
    try:
        test_historical_access(args.out_json)
    except PermissionError as error:
        raise SystemExit(str(error)) from error
    print("historical odds access works")
    print(f"saved test response to {args.out_json}")


def fetch_historical_odds(args: argparse.Namespace) -> None:
    try:
        rows = fetch_historical_totals_for_training(
            historical_games_path=args.historical_games,
            odds_out=args.out,
            raw_dir=args.raw_dir,
            max_days=args.max_days,
            snapshot_hour_utc=args.snapshot_hour_utc,
            regions=args.regions,
            bookmakers=args.bookmakers,
        )
    except PermissionError as error:
        raise SystemExit(str(error)) from error
    print(f"saved {len(rows)} historical odds rows to {args.out}")


def merge_historical_odds(args: argparse.Namespace) -> None:
    matched, total = apply_historical_odds(args.historical_games, args.odds, args.out)
    print(f"matched historical odds for {matched} of {total} historical games")
    print(f"saved merged training file to {args.out}")


def historical_template(args: argparse.Namespace) -> None:
    count = write_historical_odds_template(args.historical_games, args.out)
    print(f"saved {count} historical odds template rows to {args.out}")


def import_historical_odds(args: argparse.Namespace) -> None:
    count, skipped = normalize_historical_odds_csv(args.input, args.out)
    print(f"normalized {count} historical odds rows to {args.out}")
    if skipped:
        print(f"skipped {len(skipped)} rows that could not be parsed")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="MLB run totals model tools")
    subparsers = parser.add_subparsers(required=True)

    train_parser = subparsers.add_parser("train")
    train_parser.add_argument("--input", required=True)
    train_parser.add_argument("--model-out", required=True)
    train_parser.add_argument("--ridge-alpha", type=float, default=10.0)
    train_parser.set_defaults(func=train)

    train_b_parser = subparsers.add_parser("train-market-adjusted")
    train_b_parser.add_argument("--input", required=True)
    train_b_parser.add_argument("--model-out", required=True)
    train_b_parser.add_argument("--ridge-alpha", type=float, default=12.0)
    train_b_parser.set_defaults(func=train_market_adjusted)

    price_parser = subparsers.add_parser("price")
    price_parser.add_argument("--model", required=True)
    price_parser.add_argument("--input", required=True)
    price_parser.add_argument("--out")
    price_parser.add_argument("--preserve-existing", action="store_true")
    price_parser.set_defaults(func=price)

    price_b_parser = subparsers.add_parser("price-market-adjusted")
    price_b_parser.add_argument("--model", required=True)
    price_b_parser.add_argument("--input", required=True)
    price_b_parser.add_argument("--out")
    price_b_parser.add_argument("--preserve-existing", action="store_true")
    price_b_parser.set_defaults(func=price_market_adjusted)

    fetch_parser = subparsers.add_parser("fetch-url")
    fetch_parser.add_argument("--url", required=True)
    fetch_parser.add_argument("--out", required=True)
    fetch_parser.set_defaults(func=fetch)

    odds_parser = subparsers.add_parser("odds-current")
    odds_parser.add_argument("--out", required=True)
    odds_parser.add_argument("--api-key")
    odds_parser.add_argument("--regions", default="us")
    odds_parser.add_argument("--bookmakers")
    odds_parser.add_argument("--bookmaker")
    odds_parser.add_argument("--aggregate", choices=["median", "first"], default="median")
    odds_parser.add_argument("--features")
    odds_parser.add_argument("--raw-json")
    odds_parser.set_defaults(func=odds_current)

    odds_json_parser = subparsers.add_parser("odds-from-json")
    odds_json_parser.add_argument("--input", required=True)
    odds_json_parser.add_argument("--out", required=True)
    odds_json_parser.add_argument("--bookmaker")
    odds_json_parser.add_argument("--aggregate", choices=["median", "first"], default="median")
    odds_json_parser.add_argument("--features")
    odds_json_parser.set_defaults(func=odds_from_json)

    features_parser = subparsers.add_parser("features-today")
    features_parser.add_argument("--out", required=True)
    features_parser.add_argument("--date")
    features_parser.add_argument("--team-metrics", default="data/source/team_metrics.csv")
    features_parser.add_argument("--starter-metrics", default="data/source/starter_metrics.csv")
    features_parser.add_argument("--bullpen-metrics", default="data/source/bullpen_metrics.csv")
    features_parser.add_argument("--park-metrics", default="data/source/park_metrics.csv")
    features_parser.add_argument("--weather-metrics")
    features_parser.add_argument("--schedule-json")
    features_parser.add_argument("--raw-schedule-json")
    features_parser.set_defaults(func=features_today)

    init_parser = subparsers.add_parser("init-source-csvs")
    init_parser.add_argument("--team-metrics", default="data/source/team_metrics.csv")
    init_parser.add_argument("--starter-metrics", default="data/source/starter_metrics.csv")
    init_parser.add_argument("--bullpen-metrics", default="data/source/bullpen_metrics.csv")
    init_parser.add_argument("--park-metrics", default="data/source/park_metrics.csv")
    init_parser.add_argument("--weather-metrics", default="data/source/weather_metrics.csv")
    init_parser.set_defaults(func=init_source_csvs)

    status_parser = subparsers.add_parser("status")
    status_parser.add_argument("--root", default=".")
    status_parser.add_argument("--fail-if-missing", action="store_true")
    status_parser.set_defaults(func=status)

    update_parser = subparsers.add_parser("update-real-data")
    update_parser.add_argument("--date")
    update_parser.add_argument("--lookback-days", type=int, default=45)
    update_parser.add_argument("--team-metrics", default="data/source/team_metrics.csv")
    update_parser.add_argument("--starter-metrics", default="data/source/starter_metrics.csv")
    update_parser.add_argument("--bullpen-metrics", default="data/source/bullpen_metrics.csv")
    update_parser.add_argument("--park-metrics", default="data/source/park_metrics.csv")
    update_parser.add_argument("--weather-metrics", default="data/source/weather_metrics.csv")
    update_parser.add_argument("--historical-games", default="data/processed/historical_games.csv")
    update_parser.add_argument("--raw-dir", default="data/raw")
    update_parser.set_defaults(func=update_data)

    fg_template_parser = subparsers.add_parser("fangraphs-templates")
    fg_template_parser.add_argument("--folder", default="data/fangraphs")
    fg_template_parser.set_defaults(func=fangraphs_templates)

    fg_import_parser = subparsers.add_parser("import-fangraphs")
    fg_import_parser.add_argument("--team-batting", default="data/fangraphs/team_batting.csv")
    fg_import_parser.add_argument("--starters", default="data/fangraphs/starters.csv")
    fg_import_parser.add_argument("--bullpen", default="data/fangraphs/bullpen.csv")
    fg_import_parser.add_argument("--team-metrics-out", default="data/source/team_metrics.csv")
    fg_import_parser.add_argument("--starter-metrics-out", default="data/source/starter_metrics.csv")
    fg_import_parser.add_argument("--bullpen-metrics-out", default="data/source/bullpen_metrics.csv")
    fg_import_parser.set_defaults(func=fangraphs_import)

    weather_parser = subparsers.add_parser("update-weather")
    weather_parser.add_argument("--out", default="data/source/weather_metrics.csv")
    weather_parser.add_argument("--date")
    weather_parser.add_argument("--schedule-json")
    weather_parser.add_argument("--raw-schedule-json", default="data/raw/today_schedule.json")
    weather_parser.add_argument("--raw-weather-dir", default="data/raw/weather")
    weather_parser.set_defaults(func=weather_update)

    backtest_parser = subparsers.add_parser("backtest")
    backtest_parser.add_argument("--input", default="data/processed/historical_games.csv")
    backtest_parser.add_argument("--bets-out", default="data/processed/backtest_bets.csv")
    backtest_parser.add_argument("--summary-out", default="data/processed/backtest_summary.csv")
    backtest_parser.add_argument("--report-out", default="data/processed/backtest_report.txt")
    backtest_parser.add_argument("--min-train-games", type=int, default=200)
    backtest_parser.add_argument("--ev-threshold", type=float, default=0.03)
    backtest_parser.add_argument("--ridge-alpha", type=float, default=10.0)
    backtest_parser.set_defaults(func=backtest)

    backtest_b_parser = subparsers.add_parser("backtest-market-adjusted")
    backtest_b_parser.add_argument("--input", default="data/processed/historical_games.csv")
    backtest_b_parser.add_argument("--bets-out", default="data/processed/backtest_bets_model_b.csv")
    backtest_b_parser.add_argument("--summary-out", default="data/processed/backtest_summary_model_b.csv")
    backtest_b_parser.add_argument("--report-out", default="data/processed/backtest_report_model_b.txt")
    backtest_b_parser.add_argument("--min-train-games", type=int, default=200)
    backtest_b_parser.add_argument("--ev-threshold", type=float, default=0.03)
    backtest_b_parser.add_argument("--ridge-alpha", type=float, default=12.0)
    backtest_b_parser.set_defaults(func=backtest_market_adjusted)

    report_parser = subparsers.add_parser("report-today")
    report_parser.add_argument("--results", default="data/processed/today_results.csv")
    report_parser.add_argument("--out", default="data/processed/today_report.html")
    report_parser.add_argument("--backtest", default="data/processed/backtest_report.txt")
    report_parser.add_argument("--tracker", default="data/processed/pick_tracker.csv")
    report_parser.set_defaults(func=report_today)

    data_report_parser = subparsers.add_parser("report-data")
    data_report_parser.add_argument("--root", default=".")
    data_report_parser.add_argument("--out", default="data/processed/data_audit.html")
    data_report_parser.set_defaults(func=report_data)

    track_parser = subparsers.add_parser("track-picks")
    track_parser.add_argument("--results", default="data/processed/today_results.csv")
    track_parser.add_argument("--tracker", default="data/processed/pick_tracker.csv")
    track_parser.add_argument("--min-label", choices=["pass", "lean", "watch"], default="lean")
    track_parser.set_defaults(func=track_picks)

    grade_parser = subparsers.add_parser("grade-picks")
    grade_parser.add_argument("--tracker", default="data/processed/pick_tracker.csv")
    grade_parser.add_argument("--report-out", default="data/processed/pick_tracker_report.txt")
    grade_parser.set_defaults(func=grade_picks)

    remove_date_parser = subparsers.add_parser("remove-tracked-date")
    remove_date_parser.add_argument("--date", required=True)
    remove_date_parser.add_argument("--tracker", default="data/processed/pick_tracker.csv")
    remove_date_parser.add_argument("--report-out", default="data/processed/pick_tracker_report.txt")
    remove_date_parser.set_defaults(func=remove_tracked_date)

    document_parser = subparsers.add_parser("document-games")
    document_parser.add_argument("--date")
    document_parser.add_argument("--out-csv", default="data/processed/yesterday_games.csv")
    document_parser.add_argument("--out-html", default="data/processed/yesterday_games.html")
    document_parser.add_argument("--tracker", default="data/processed/pick_tracker.csv")
    document_parser.set_defaults(func=document_games_cmd)

    archive_parser = subparsers.add_parser("archive-current")
    archive_parser.add_argument("--results", default="data/processed/today_results.csv")
    archive_parser.add_argument("--report", default="data/processed/today_report.html")
    archive_parser.set_defaults(func=archive_outputs)

    access_parser = subparsers.add_parser("historical-odds-access")
    access_parser.add_argument("--out-json", default="data/raw/historical_access_test.json")
    access_parser.set_defaults(func=historical_access)

    historical_parser = subparsers.add_parser("fetch-historical-odds")
    historical_parser.add_argument("--historical-games", default="data/processed/historical_games.csv")
    historical_parser.add_argument("--out", default="data/raw/historical_totals.csv")
    historical_parser.add_argument("--raw-dir", default="data/raw/historical_odds")
    historical_parser.add_argument("--max-days", type=int, default=7)
    historical_parser.add_argument("--snapshot-hour-utc", type=int, default=16)
    historical_parser.add_argument("--regions", default="us")
    historical_parser.add_argument("--bookmakers")
    historical_parser.set_defaults(func=fetch_historical_odds)

    merge_parser = subparsers.add_parser("merge-historical-odds")
    merge_parser.add_argument("--historical-games", default="data/processed/historical_games.csv")
    merge_parser.add_argument("--odds", default="data/raw/historical_totals.csv")
    merge_parser.add_argument("--out", default="data/processed/historical_games_with_real_odds.csv")
    merge_parser.set_defaults(func=merge_historical_odds)

    template_parser = subparsers.add_parser("historical-odds-template")
    template_parser.add_argument("--historical-games", default="data/processed/historical_games.csv")
    template_parser.add_argument("--out", default="data/raw/historical_totals_template.csv")
    template_parser.set_defaults(func=historical_template)

    import_parser = subparsers.add_parser("import-historical-odds")
    import_parser.add_argument("--input", required=True)
    import_parser.add_argument("--out", default="data/raw/historical_totals_imported.csv")
    import_parser.set_defaults(func=import_historical_odds)

    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
