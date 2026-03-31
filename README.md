# 🤖 Mission Control

Roborto's personal mission control dashboard — a sleek dark-themed status page showing system metrics, the daily brief status, cron jobs, and quick links.

**Live, auto-refreshing. No build tools. Pure vanilla HTML/CSS/JS.**

---

## What's in here

| File | Purpose |
|------|---------|
| `index.html` | Full dashboard — all CSS and JS inline in one file |
| `pusher.py` | Python 3 metrics collector (stdlib only) — runs every 5 min via cron |
| `metrics.json` | Live data file read by the dashboard |
| `README.md` | This file |

### Dashboard sections

- **🤖 Roborto Status** — last seen, model, online/offline pill
- **💻 Machine Monitor** — CPU sparkline (last 20 readings), RAM bar, disk bar, uptime
- **🗞️ Daily Brief** — article counts by section, last updated time, link to open the brief
- **📊 Tryadd Watch** — latest articles from the `🐄 Tryadd Watch` section of the brief
- **⏱️ Cron Jobs** — all OpenClaw jobs with schedule, last run, next run
- **🔗 Quick Links** — Tryadd, GitHub, Daily Brief, AtomicMail

---

## Deploy to Vercel

1. Push this repo to GitHub (or make sure `mission-control/` is in your repo).
2. Go to [vercel.com](https://vercel.com) → **Add New Project** → Import your repo.
3. Set **Root Directory** to `mission-control/` (or the subfolder it lives in).
4. **Framework Preset**: Other (static)
5. Hit **Deploy**. That's it — Vercel serves `index.html` as-is.

> **Live metrics on Vercel:** By default the dashboard fetches `/metrics.json` relative to the page. On Vercel, `metrics.json` is static. To get live updates you need to push metrics to a GitHub Gist and point the dashboard at the raw URL (see below).

---

## Live metrics via GitHub Gist

This lets the dashboard stay fresh even when hosted on Vercel (or anywhere without server-side code).

### Step 1 — Create a Gist

1. Go to [gist.github.com](https://gist.github.com)
2. Create a new **secret** gist named `metrics.json` with `{}` as content.
3. Copy the **Gist ID** from the URL: `gist.github.com/Mr-Roborto2716/<GIST_ID>`

### Step 2 — Create a GitHub token

1. Go to [github.com/settings/tokens](https://github.com/settings/tokens) → **Generate new token (classic)**
2. Scope: **`gist`** only
3. Copy the token

### Step 3 — Create the config file

```bash
cat > ~/.openclaw/mission-control-config.json << 'EOF'
{
  "gist_id": "YOUR_GIST_ID_HERE",
  "github_token": "ghp_YOUR_TOKEN_HERE"
}
EOF
```

### Step 4 — Point the dashboard at the Gist

Add this before the closing `</body>` in `index.html` (or set it in Vercel environment as a static injection):

```html
<script>
  window.METRICS_URL = 'https://gist.githubusercontent.com/Mr-Roborto2716/YOUR_GIST_ID/raw/metrics.json';
</script>
```

> You'll need to add `?nocache=1` or similar since GitHub Gist raw URLs are cached. The pusher already busts the cache in the dashboard via `?_=<timestamp>`.

---

## metrics.json format

```json
{
  "updated_at": "2026-03-31T00:00:00+00:00",
  "machine": {
    "hostname": "ASULinux",
    "uptime_seconds": 12345,
    "boot_time": "2026-03-30T12:00:00+00:00",
    "load_1": 0.5,
    "load_5": 0.5,
    "load_15": 0.5,
    "ram_total_mb": 8000,
    "ram_used_mb": 3000,
    "ram_available_mb": 5000,
    "disk_total_gb": 187,
    "disk_used_gb": 8.7,
    "disk_free_gb": 169,
    "disk_pct": 5,
    "tailscale_ip": "100.108.159.44"
  },
  "roborto": {
    "last_seen": "2026-03-31T00:00:00+00:00",
    "model": "anthropic/claude-sonnet-4-6",
    "status": "online"
  },
  "brief": {
    "last_updated": "2026-03-30T23:43:07+00:00",
    "article_counts": {
      "🤖 AI & ML": 8,
      "🎮 Gaming & Pop Culture": 8
    },
    "total_articles": 53,
    "tryadd_latest": [
      {"title": "Article Title", "link": "https://...", "_source": "Feed Name"}
    ]
  },
  "cron_jobs": [
    {
      "name": "Daily Brief - Fetch Feeds",
      "schedule": "45 13 * * *",
      "next_run": "2026-04-01T13:45:00+00:00",
      "last_run": null,
      "enabled": true
    }
  ],
  "history": {
    "load_1": [0.5, 0.4, 0.6],
    "ram_used_pct": [40, 41, 42]
  }
}
```

---

## How the cron pusher works

`pusher.py` is run every 5 minutes by OpenClaw cron:

1. Reads `/proc/loadavg`, `/proc/meminfo`, `/proc/uptime` → system metrics
2. Reads `daily-brief/data.json` → article counts + latest Tryadd articles
3. Reads `~/.openclaw/cron/jobs.json` → cron job list
4. Loads existing `metrics.json` → appends to history arrays (keeps last 20 readings)
5. Writes fresh `metrics.json`
6. If `~/.openclaw/mission-control-config.json` has `gist_id` + `github_token` → PATCHes the Gist

---

*Built by Roborto. Powered by OpenClaw.*
