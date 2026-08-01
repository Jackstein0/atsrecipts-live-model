# MLB Run Totals Betting Model

Small, dependency-light scaffold for modeling MLB full-game run totals.

The workflow is:

1. Cache raw FanGraphs/export CSVs or local source files.
2. Build one row per game with pregame-only features.
3. Train a regularized linear model for expected combined runs.
4. Convert expected runs to over/under probabilities.
5. Compare those probabilities to market totals and prices.

This is not betting advice. It is a research scaffold for backtesting and model development.

## Quick Start

```bash
cd /Users/jacksteinkoenig/Documents/Codex/2026-06-28/can/outputs/run_totals_model
bash scripts/demo.sh
```

That demo trains on sample rows, parses a sample odds response, merges odds with sample features, and prints a ranked totals board. The numbers are not real betting signals.

If you want the normal input folders prefilled with sample data:

```bash
bash scripts/load_sample_data.sh
```

This creates sample versions of `data/source/*.csv` and `data/processed/historical_games.csv`. Replace them before trusting any output.

## Daily Use

1. Copy `.env.example` to `.env` and add your The Odds API key.
2. Put historical training rows at `data/processed/historical_games.csv`.
3. Create and fill the source metric CSVs.
4. Run:

```bash
bash scripts/run_today.sh
```

The script will:

- update real MLB-derived source data from public MLB endpoints
- overlay FanGraphs exports from `data/fangraphs` when those CSVs exist
- refresh weather from Open-Meteo using ballpark coordinates
- train `data/processed/totals_model.json` if it does not exist
- build `data/processed/today_features.csv` from MLB schedule/probables plus your source metrics
- fetch current MLB totals from The Odds API
- merge those odds into the feature file
- print the model's over/under probabilities and EVs
- save a readable HTML report at `data/processed/today_report.html`
- append all `watch` and `lean` picks to `data/processed/pick_tracker.csv`
- grade completed tracked picks and update `data/processed/pick_tracker_report.txt`

## Backtest

Run:

```bash
bash scripts/run_backtest.sh
```

Outputs:

- `data/processed/backtest_report.txt`
- `data/processed/backtest_summary.csv`
- `data/processed/backtest_bets.csv`

The backtest walks forward through `historical_games.csv`, training only on prior rows before pricing each later game. The current generated historical file uses real MLB scores but proxy market totals unless you replace it with true historical sportsbook totals and odds.

## Model B: Market-Adjusted Totals

The original model predicts expected total runs directly from baseball inputs. Model B uses a different logic: it starts with the sportsbook total as the baseline and trains on the residual gap between actual total runs and the market total.

Model B features are engineered from:

- combined and relative offense (`wRC+`)
- combined and relative starter quality (`xFIP`)
- combined and relative bullpen quality (`xFIP`)
- park factor
- temperature and wind out

Run its walk-forward backtest without overwriting the original backtest:

```bash
bash scripts/run_model_b_backtest.sh
```

Outputs:

- `data/processed/backtest_report_model_b.txt`
- `data/processed/backtest_summary_model_b.csv`
- `data/processed/backtest_bets_model_b.csv`

Train and price it manually:

```bash
PYTHONPATH=src python3 -m run_totals_model.cli train-market-adjusted \
  --input data/processed/historical_games.csv \
  --model-out data/processed/totals_model_b.json

PYTHONPATH=src python3 -m run_totals_model.cli price-market-adjusted \
  --model data/processed/totals_model_b.json \
  --input data/processed/today_board.csv \
  --out data/processed/today_results_model_b.csv
```

## Historical Odds Upgrade

If your The Odds API plan includes historical odds:

```bash
bash scripts/run_historical_odds_upgrade.sh
```

This tests access, fetches recent historical MLB totals, merges them into the training file, and runs a second backtest.

Outputs:

- `data/raw/historical_totals.csv`
- `data/processed/historical_games_with_real_odds.csv`
- `data/processed/backtest_report_real_odds.txt`

If your plan does not include historical odds, the script will stop with a clear message. You can still import a historical totals CSV from another source as long as it has `date`, `away_team`, `home_team`, `market_total`, `over_odds`, and `under_odds`.

To create a fill-in template for another historical odds source:

```bash
bash scripts/make_historical_odds_template.sh
```

Template:

- `data/raw/historical_totals_template.csv`

After filling that file, run:

```bash
bash scripts/import_historical_odds.sh
```

The importer also accepts common export column names such as `Date`, `Away`, `Home`, `Total`, `Over`, and `Under`.

To create blank source templates:

```bash
PYTHONPATH=src python3 -m run_totals_model.cli init-source-csvs
```

Fill these files:

```csv
data/source/team_metrics.csv
team,wrc_plus

data/source/starter_metrics.csv
mlbam_id,pitcher_name,xfip

data/source/bullpen_metrics.csv
team,bullpen_xfip

data/source/park_metrics.csv
team,park_factor

data/source/weather_metrics.csv
game_id,temp_f,wind_out_mph
```

Those source files are intentionally simple. Pull or export the values from FanGraphs, paste/cache them there, and the daily script handles the joining.

You can override paths without editing the script:

```bash
MODEL=data/processed/sample_model.json \
FEATURES=examples/today_board.csv \
bash scripts/run_today.sh
```

## Input Shape

Training rows need one row per game:

```csv
date,away_team,home_team,away_runs,home_runs,market_total,over_odds,under_odds,home_wrc_plus,away_wrc_plus,home_sp_xfip,away_sp_xfip,home_bullpen_xfip,away_bullpen_xfip,park_factor,temp_f,wind_out_mph
```

The model target is `away_runs + home_runs`. Feature columns are inferred from numeric columns except outcomes and market odds.

Pricing rows need the same pregame feature columns plus:

```csv
date,away_team,home_team,market_total,over_odds,under_odds
```

## FanGraphs Ingestion

Use cached URLs rather than scraping pages repeatedly:

```bash
PYTHONPATH=src python3 -m run_totals_model.cli fetch-url \
  --url "https://example.com/export.csv" \
  --out data/raw/fangraphs_export.csv
```

For FanGraphs specifically, prefer official page export/download CSVs where available, cache responses, and keep request volume low.

## Odds Ingestion

Current MLB totals can be pulled from The Odds API. Set an API key first:

```bash
export THE_ODDS_API_KEY="..."
PYTHONPATH=src python3 -m run_totals_model.cli odds-current \
  --out data/raw/today_odds.csv \
  --raw-json data/raw/today_odds.json
```

To merge current odds with a pregame feature file:

```bash
PYTHONPATH=src python3 -m run_totals_model.cli odds-current \
  --features data/processed/today_features.csv \
  --out data/processed/today_board.csv
```

Then price the board:

```bash
PYTHONPATH=src python3 -m run_totals_model.cli price \
  --model data/processed/totals_model.json \
  --input data/processed/today_board.csv
```

The Odds API supports `baseball_mlb` with `markets=totals` and `oddsFormat=american`. By default this scaffold takes the median total and prices across returned books. Use `--bookmakers draftkings` or `--bookmaker draftkings` if you want a specific shop.

For historical backtests, use either The Odds API's historical endpoints if your plan supports them, or import a historical totals CSV into the training schema above. The model needs odds that were available before first pitch, not final/closing data accidentally joined after the fact.

## Feature Generation

## FanGraphs Exports

Create drop-zone templates:

```bash
PYTHONPATH=src python3 -m run_totals_model.cli fangraphs-templates
```

Then replace:

- `data/fangraphs/team_batting.csv`
- `data/fangraphs/starters.csv`
- `data/fangraphs/bullpen.csv`

Run:

```bash
PYTHONPATH=src python3 -m run_totals_model.cli import-fangraphs
```

`Run Today.command` does that import automatically whenever the FanGraphs files exist.

## Weather

Weather is refreshed automatically in the daily run:

```bash
PYTHONPATH=src python3 -m run_totals_model.cli update-weather
```

It uses Open-Meteo with built-in MLB ballpark coordinates. Domed/retractable-roof parks are set to zero wind impact.

## Feature Generation

To refresh the model inputs with real MLB-derived data:

```bash
PYTHONPATH=src python3 -m run_totals_model.cli update-real-data
```

This uses recent completed MLB games and today's probable starters. It creates real-data proxies for the current scaffold:

- `wrc_plus` = recent team runs per game indexed to league average
- `starter xfip` = current pitcher ERA proxy from MLB stats
- `bullpen_xfip` = recent team runs allowed per game proxy
- park factor = built-in park-factor table

These are real baseball data inputs, but they are still proxies. Replace them with FanGraphs exports when you want sharper features.

Today's feature file can be generated directly:

```bash
PYTHONPATH=src python3 -m run_totals_model.cli features-today \
  --out data/processed/today_features.csv \
  --raw-schedule-json data/raw/today_schedule.json
```

By default this reads:

- `data/source/team_metrics.csv`
- `data/source/starter_metrics.csv`
- `data/source/bullpen_metrics.csv`
- `data/source/park_metrics.csv`

It fetches the MLB schedule and probable starters from the public MLB Stats API and caches the raw schedule when `--raw-schedule-json` is provided. For an offline test, use:

```bash
PYTHONPATH=src python3 -m run_totals_model.cli features-today \
  --schedule-json examples/mlb_schedule_sample.json \
  --team-metrics examples/source/team_metrics.csv \
  --starter-metrics examples/source/starter_metrics.csv \
  --bullpen-metrics examples/source/bullpen_metrics.csv \
  --park-metrics examples/source/park_metrics.csv \
  --weather-metrics examples/source/weather_metrics.csv \
  --out data/processed/sample_today_features.csv
```

## Next Data To Add

- FanGraphs team batting projections: wRC+, BB%, K%, ISO split by pitcher handedness.
- FanGraphs probable starter stats or projections: xFIP, SIERA, K-BB%, pitch count/recent workload.
- Bullpen quality and rest: xFIP, leverage usage in last 1/3/5 days.
- Park factors and weather: temperature, wind direction/speed, roof status.
- Odds history: opening total, current total, over/under prices, closing line.
