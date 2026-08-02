from __future__ import annotations

import argparse
import csv
import html
import json
import shutil
from pathlib import Path


MODEL_B_BACKTEST = {
    "title": "Model B Backtest",
    "games": "361",
    "bets": "184",
    "record": "99-78-7",
    "profit": "+12.00 units",
    "roi": "6.52%",
    "ev": "8.85%",
}

ORIGINAL_BACKTEST = {
    "title": "Original Model Backtest",
    "games": "400",
    "bets": "229",
    "record": "122-97-10",
    "profit": "+13.91 units",
    "roi": "6.07%",
    "ev": "10.98%",
}


def load_rows(path: str) -> list[dict[str, str]]:
    target = Path(path)
    if not target.exists():
        return []
    with target.open(newline="") as handle:
        return list(csv.DictReader(handle))


def write_combined_report(
    original_path: str,
    model_b_path: str,
    out_path: str,
    generated_label: str,
    logo_path: str | None = None,
    tracker_path: str = "data/processed/pick_tracker.csv",
    model_b_tracker_path: str = "data/processed/pick_tracker_model_b.csv",
) -> None:
    original_rows = load_rows(original_path)
    model_b_rows = load_rows(model_b_path)
    original_dates = _active_dates(original_rows)
    model_b_dates = _active_dates(model_b_rows)
    tracked = _tracked_summary(tracker_path, original_dates)
    model_b_tracked = _tracked_summary(model_b_tracker_path, model_b_dates)
    out = Path(out_path)
    out.parent.mkdir(parents=True, exist_ok=True)

    if logo_path and Path(logo_path).exists():
        assets_dir = out.parent / "assets"
        assets_dir.mkdir(parents=True, exist_ok=True)
        source_logo = Path(logo_path)
        target_logo = assets_dir / "brewers-logo-wallpaper.png"
        if source_logo.resolve() != target_logo.resolve():
            shutil.copy2(source_logo, target_logo)

    html_text = _page(
        original_rows=original_rows,
        model_b_rows=model_b_rows,
        generated_label=generated_label,
        original_tracked=tracked,
        model_b_tracked=model_b_tracked,
    )
    out.write_text(html_text)


def _active_dates(rows: list[dict[str, str]]) -> set[str]:
    return {row.get("date", "") for row in rows if row.get("date")}


def _tracked_summary(tracker_path: str, active_dates: set[str] | None = None) -> dict[str, str]:
    rows = load_rows(tracker_path)
    settled = [row for row in rows if row.get("result") in {"win", "loss", "push"}]
    pending = [
        row
        for row in rows
        if (row.get("result") or "pending") == "pending"
        and (not active_dates or row.get("date") in active_dates)
    ]
    wins = sum(1 for row in settled if row.get("result") == "win")
    losses = sum(1 for row in settled if row.get("result") == "loss")
    pushes = sum(1 for row in settled if row.get("result") == "push")
    units = sum(float(row.get("profit_units") or 0) for row in settled)
    roi = units / len(settled) if settled else 0.0
    return {
        "record": f"{wins}-{losses}-{pushes}",
        "units": f"{units:+.2f}",
        "roi": f"{roi:.1%}",
        "status": f"{len(pending)} pending today",
    }


def _page(
    original_rows: list[dict[str, str]],
    model_b_rows: list[dict[str, str]],
    generated_label: str,
    original_tracked: dict[str, str],
    model_b_tracked: dict[str, str],
) -> str:
    payload = {
        "modelB": {
            "title": "Model B Games",
            "label": "Market-adjusted",
            "rows": model_b_rows,
            "tracked": model_b_tracked,
            "backtest": MODEL_B_BACKTEST,
        },
        "original": {
            "title": "Original Model Games",
            "label": "Original totals",
            "rows": original_rows,
            "tracked": original_tracked,
            "backtest": ORIGINAL_BACKTEST,
        },
    }
    data_json = json.dumps(payload)
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>MLB Run Totals Report</title>
  <style>
    :root {{
      color-scheme: light;
      --ink: #1d2329;
      --muted: #52606d;
      --line: #dfe3e8;
      --soft-line: #eef1f4;
      --gold: #ffc52f;
      --cream: #fff1c2;
      --green: #135c31;
      --red: #8d3027;
      --white: rgba(255, 255, 255, 0.97);
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      color: var(--ink);
      background:
        radial-gradient(circle at 18% 12%, rgba(255, 197, 47, 0.20), transparent 28%),
        radial-gradient(circle at 82% 18%, rgba(255, 197, 47, 0.12), transparent 24%),
        linear-gradient(135deg, #102d59 0%, #1c3d70 48%, #0d2448 100%);
      background-attachment: fixed;
      min-height: 100vh;
    }}
    body::before {{
      content: "";
      position: fixed;
      inset: 0;
      z-index: 0;
      background: url("assets/brewers-logo-wallpaper.png") center 80px / min(72vw, 860px) auto no-repeat fixed;
      opacity: 0.16;
      pointer-events: none;
    }}
    header, main {{ position: relative; z-index: 1; }}
    header {{
      padding: 24px;
      color: white;
      background: rgba(7, 26, 54, 0.92);
      border-bottom: 4px solid var(--gold);
    }}
    h1 {{ margin: 0; font-size: 30px; font-weight: 760; letter-spacing: 0; }}
    .subtitle {{ margin-top: 14px; color: rgba(255, 255, 255, 0.9); font-size: 16px; font-weight: 600; }}
    main {{ max-width: 1120px; margin: 0 auto; padding: 20px; }}
    .notice {{
      color: white;
      font-size: 16px;
      font-weight: 650;
      line-height: 1.45;
      margin: 0 0 14px;
      text-shadow: 0 1px 2px rgba(0, 0, 0, 0.45);
    }}
    .toolbar {{ display: flex; align-items: center; gap: 12px; flex-wrap: wrap; margin-bottom: 14px; }}
    .tabs {{
      display: inline-flex;
      gap: 0;
      padding: 4px;
      border-radius: 10px;
      background: rgba(7, 26, 54, 0.42);
      border: 1px solid rgba(255, 255, 255, 0.42);
    }}
    .tab {{
      display: inline-flex;
      align-items: center;
      height: 34px;
      padding: 0 14px;
      border: 0;
      border-radius: 8px;
      background: transparent;
      color: rgba(255, 255, 255, 0.82);
      font-weight: 700;
      font-size: 14px;
      cursor: pointer;
    }}
    .tab.active {{ background: white; color: #0d2448; box-shadow: 0 1px 4px rgba(0, 0, 0, 0.18); }}
    .stat-row {{
      display: grid;
      grid-template-columns: repeat(5, minmax(120px, 1fr));
      gap: 0;
      margin-bottom: 16px;
      background: var(--white);
      border: 1px solid var(--line);
      border-radius: 8px;
      padding: 14px;
    }}
    .stat {{ padding: 4px 10px; min-height: 56px; }}
    .stat-label {{ color: #2b3238; font-size: 14px; font-weight: 700; }}
    .stat-value {{ margin-top: 8px; color: #333b42; font-size: 16px; font-weight: 600; }}
    .panel {{
      background: var(--white);
      border: 1px solid var(--line);
      border-radius: 8px;
      padding: 14px;
      margin-top: 16px;
      overflow-x: auto;
    }}
    .panel h2 {{ margin: 0 0 8px; font-size: 24px; line-height: 1.15; }}
    .panel p {{ margin: 8px 0 0; color: #33404a; line-height: 1.45; font-size: 14px; }}
    .comparison {{
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(260px, 1fr));
      gap: 12px;
      margin-top: 10px;
    }}
    .mini-card {{
      border: 1px solid var(--soft-line);
      border-radius: 8px;
      padding: 12px;
      background: rgba(255, 255, 255, 0.72);
    }}
    .mini-card h3 {{ margin: 0 0 8px; font-size: 16px; }}
    .line {{
      display: flex;
      justify-content: space-between;
      gap: 12px;
      padding: 5px 0;
      border-bottom: 1px solid var(--soft-line);
      font-size: 14px;
    }}
    .line:last-child {{ border-bottom: 0; }}
    .line span:last-child {{ font-weight: 750; font-variant-numeric: tabular-nums; text-align: right; }}
    .grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(280px, 1fr)); gap: 12px; }}
    table {{ width: 100%; border-collapse: collapse; margin-top: 10px; }}
    td {{ padding: 4px 0; border-bottom: 1px solid var(--soft-line); font-size: 14px; }}
    tr:last-child td {{ border-bottom: 0; }}
    .card {{ background: var(--white); border: 1px solid var(--line); border-radius: 8px; padding: 14px; }}
    .teams {{ font-size: 18px; font-weight: 750; margin-bottom: 8px; }}
    .meta {{ color: var(--muted); font-size: 13px; margin-bottom: 12px; }}
    .pick {{ display: inline-block; padding: 4px 8px; border-radius: 999px; font-weight: 750; text-transform: uppercase; }}
    .card td:last-child {{ text-align: right; font-variant-numeric: tabular-nums; padding-left: 12px; }}
    .watch {{ background: var(--cream); color: #5c4300; }}
    .lean {{ background: #dff5e8; color: var(--green); }}
    .pass {{ background: #edf0f3; color: var(--muted); }}
    .side-over {{ color: var(--green); }}
    .side-under {{ color: var(--red); }}
    .empty {{ padding: 34px; color: var(--muted); text-align: center; background: var(--white); border: 1px solid var(--line); border-radius: 8px; }}
    @media (max-width: 760px) {{
      header, main {{ padding-left: 14px; padding-right: 14px; }}
      .stat-row {{ grid-template-columns: repeat(2, minmax(120px, 1fr)); gap: 10px; }}
    }}
  </style>
</head>
<body>
  <header>
    <h1>MLB Run Totals Report</h1>
    <div class="subtitle">Generated {html.escape(generated_label)}</div>
  </header>
  <main>
    <p class="notice">This is a research report, not betting advice. Watch and lean are tracked; pass is shown for context only.</p>
    <div class="toolbar">
      <div class="tabs" role="tablist" aria-label="Model selector">
        <button class="tab active" type="button" data-model="modelB">Model B</button>
        <button class="tab" type="button" data-model="original">Original Model</button>
      </div>
    </div>
    <section class="stat-row" aria-label="Board summary">
      <div class="stat"><div class="stat-label">Games</div><div class="stat-value" id="gamesStat">0</div></div>
      <div class="stat"><div class="stat-label">Watch</div><div class="stat-value" id="watchStat">0</div></div>
      <div class="stat"><div class="stat-label">Lean</div><div class="stat-value" id="leanStat">0</div></div>
      <div class="stat"><div class="stat-label">Best EV</div><div class="stat-value" id="evStat">--</div></div>
      <div class="stat"><div class="stat-label">Model</div><div class="stat-value" id="modelStat">Market-adjusted</div></div>
    </section>
    <section class="panel">
      <h2>Model Records</h2>
      <div class="comparison" id="modelRecords"></div>
    </section>
    <section class="panel">
      <h2 id="boardTitle">Model B Games</h2>
      <div id="board"></div>
    </section>
    <section class="panel">
      <h2>Backtest Record</h2>
      <div class="comparison" id="backtestRecord"></div>
      <p>Important: the historical market totals in this scaffold may include proxy lines unless replaced with real pregame sportsbook totals and odds.</p>
    </section>
  </main>
  <script>
    const models = {data_json};

    function formatPercent(value) {{
      const number = Number(value);
      if (!Number.isFinite(number)) return "";
      return `${{(number * 100).toFixed(1)}}%`;
    }}

    function formatNumber(value, digits = 2) {{
      const number = Number(value);
      if (!Number.isFinite(number)) return value ?? "";
      return number.toFixed(digits);
    }}

    function escapeHtml(value) {{
      return String(value ?? "")
        .replaceAll("&", "&amp;")
        .replaceAll("<", "&lt;")
        .replaceAll(">", "&gt;")
        .replaceAll('"', "&quot;")
        .replaceAll("'", "&#039;");
    }}

    function formatTime(value) {{
      if (!value) return "";
      const date = new Date(value);
      if (Number.isNaN(date.getTime())) return value;
      return date.toLocaleTimeString([], {{ hour: "numeric", minute: "2-digit" }});
    }}

    function weatherText(row) {{
      const temp = formatNumber(row.temp_f, 1);
      const wind = formatNumber(row.wind_mph, 1);
      const out = formatNumber(row.wind_out_mph, 1);
      const roof = row.roof || "";
      return `${{temp}} F, ${{wind}} mph wind, out ${{out}}, roof ${{roof}}`;
    }}

    function miniCard(title, rows) {{
      return `
        <div class="mini-card">
          <h3>${{escapeHtml(title)}}</h3>
          ${{rows.map(([label, value]) => `<div class="line"><span>${{escapeHtml(label)}}</span><span>${{escapeHtml(value)}}</span></div>`).join("")}}
        </div>
      `;
    }}

    function renderRecords() {{
      document.getElementById("modelRecords").innerHTML = miniCard("Model B", [
        ["Tracked record", models.modelB.tracked.record],
        ["Units", models.modelB.tracked.units],
        ["ROI", models.modelB.tracked.roi],
        ["Status", models.modelB.tracked.status],
      ]) + miniCard("Original Model", [
        ["Tracked record", models.original.tracked.record],
        ["Units", models.original.tracked.units],
        ["ROI", models.original.tracked.roi],
        ["Status", models.original.tracked.status],
      ]);
    }}

    function render(modelKey) {{
      const model = models[modelKey];
      const rows = [...model.rows].sort((a, b) => {{
        const timeA = Date.parse(a.commence_time || "");
        const timeB = Date.parse(b.commence_time || "");
        if (Number.isFinite(timeA) && Number.isFinite(timeB)) return timeA - timeB;
        if (Number.isFinite(timeA)) return -1;
        if (Number.isFinite(timeB)) return 1;
        return ((a.away_team || "") + " " + (a.home_team || "")).localeCompare((b.away_team || "") + " " + (b.home_team || ""));
      }});
      document.getElementById("gamesStat").textContent = rows.length;
      document.getElementById("watchStat").textContent = rows.filter((row) => row.edge_label === "watch").length;
      document.getElementById("leanStat").textContent = rows.filter((row) => row.edge_label === "lean").length;
      document.getElementById("modelStat").textContent = model.label;
      document.getElementById("boardTitle").textContent = model.title;

      const bestEv = rows.reduce((best, row) => Math.max(best, Number(row.best_ev)), -Infinity);
      document.getElementById("evStat").textContent = Number.isFinite(bestEv) ? formatPercent(bestEv) : "--";

      const board = document.getElementById("board");
      if (rows.length === 0) {{
        board.innerHTML = '<div class="empty">No games are priced in this file yet.</div>';
        return;
      }}

      board.innerHTML = `
        <section class="grid">
          ${{rows.map((row) => {{
            const label = String(row.edge_label || "pass").toLowerCase();
            const side = String(row.best_side || "").toLowerCase();
            const tracked = label === "pass" ? "NOT TRACKED: PASS" : label;
            return `
              <article class="card">
                <div class="teams">${{escapeHtml(row.away_team)}} @ ${{escapeHtml(row.home_team)}}</div>
                <div class="meta">${{escapeHtml(row.date)}} · ${{formatTime(row.commence_time)}} · total ${{formatNumber(row.market_total, 1)}}</div>
                <div class="pick ${{label}}">${{escapeHtml(tracked)}}: <span class="side-${{side}}">${{escapeHtml(side)}}</span></div>
                <table>
                  <tr><td>Model total</td><td>${{formatNumber(row.model_total, 2)}}</td></tr>
                  <tr><td>Best EV</td><td>${{formatPercent(row.best_ev)}}</td></tr>
                  <tr><td>Over probability</td><td>${{formatPercent(row.over_probability)}}</td></tr>
                  <tr><td>Under probability</td><td>${{formatPercent(row.under_probability)}}</td></tr>
                  <tr><td>Sportsbook</td><td>${{escapeHtml(row.sportsbook)}}</td></tr>
                  <tr><td>Weather</td><td>${{escapeHtml(weatherText(row))}}</td></tr>
                  <tr><td>Starters</td><td>${{escapeHtml(row.away_sp_name || "TBD")}} / ${{escapeHtml(row.home_sp_name || "TBD")}}</td></tr>
                </table>
              </article>
            `;
          }}).join("")}}
        </section>
      `;

      const backtest = model.backtest;
      document.getElementById("backtestRecord").innerHTML = miniCard(backtest.title, [
        ["Games tested", backtest.games],
        ["Bets placed", backtest.bets],
        ["Record", backtest.record],
        ["Profit", backtest.profit],
        ["ROI", backtest.roi],
        ["Average EV", backtest.ev],
      ]);
    }}

    document.querySelectorAll(".tab").forEach((tab) => {{
      tab.addEventListener("click", () => {{
        document.querySelectorAll(".tab").forEach((button) => button.classList.remove("active"));
        tab.classList.add("active");
        render(tab.dataset.model);
      }});
    }});

    renderRecords();
    render("modelB");
  </script>
</body>
</html>
"""


def main() -> None:
    parser = argparse.ArgumentParser(description="Write a combined original/Model B HTML report.")
    parser.add_argument("--original", default="data/processed/today_results.csv")
    parser.add_argument("--model-b", default="data/processed/today_results_model_b.csv")
    parser.add_argument("--out", default="data/processed/model_report.html")
    parser.add_argument("--generated-label", required=True)
    parser.add_argument("--logo", default="data/processed/assets/brewers-logo-wallpaper.png")
    parser.add_argument("--tracker", default="data/processed/pick_tracker.csv")
    parser.add_argument("--model-b-tracker", default="data/processed/pick_tracker_model_b.csv")
    args = parser.parse_args()
    write_combined_report(
        original_path=args.original,
        model_b_path=args.model_b,
        out_path=args.out,
        generated_label=args.generated_label,
        logo_path=args.logo,
        tracker_path=args.tracker,
        model_b_tracker_path=args.model_b_tracker,
    )
    print(f"saved combined model report to {args.out}")


if __name__ == "__main__":
    main()
