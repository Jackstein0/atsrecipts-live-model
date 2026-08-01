# Deploying the MLB Model Site

Recommended public URL:

```text
picks.atsrecipts.com
```

## What This App Does

`web_app.py` serves the combined model report. When someone refreshes the site, it checks whether the board is older than `BOARD_MAX_AGE_SECONDS`. If it is stale, the server runs:

```bash
bash scripts/update_all_model_boards.sh
```

The HTML report is served from:

```text
data/processed/model_report.html
```

## Required Environment Variables

Set these on the hosting service, not inside the HTML:

```text
THE_ODDS_API_KEY=your odds API key
BOARD_MAX_AGE_SECONDS=900
REFRESH_ON_VIEW=1
BOARD_UPDATE_TIMEOUT_SECONDS=240
CRON_SECRET=make-a-random-secret
```

`BOARD_MAX_AGE_SECONDS=900` means normal page refreshes can update the board at most once every 15 minutes.

## Render Setup

1. Push this folder to GitHub.
2. In Render, create a new **Web Service** from that repo.
3. Use these settings:

```text
Build Command: pip install -r requirements.txt
Start Command: gunicorn web_app:app --bind 0.0.0.0:$PORT --timeout 300
```

4. Add the environment variables above.
5. Open the Render URL once and confirm the board loads.

Optional scheduled updater:

Create a Render Cron Job that runs every 15 or 30 minutes and calls:

```bash
curl -fsS "https://YOUR-RENDER-URL.onrender.com/refresh?secret=$CRON_SECRET"
```

## Cloudflare DNS

After the hosting service gives you a live URL, add this DNS record in Cloudflare:

```text
Type: CNAME
Name: picks
Target: YOUR-HOSTING-TARGET
Proxy: Proxied / orange cloud
```

Then add `picks.atsrecipts.com` as a custom domain on the hosting service if it requires domain verification.
