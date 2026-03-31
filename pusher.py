#!/usr/bin/env python3
"""
Mission Control Metrics Pusher
Collects system metrics and writes metrics.json for the dashboard.
Optionally pushes to GitHub Gist.

No external dependencies — stdlib only.
"""

import json
import os
import socket
import struct
import time
import urllib.request
import urllib.error
from datetime import datetime, timezone

# Paths
WORKSPACE = "/home/asulinux/.openclaw/workspace"
MISSION_CONTROL_DIR = os.path.join(WORKSPACE, "mission-control")
METRICS_FILE = os.path.join(MISSION_CONTROL_DIR, "metrics.json")
DAILY_BRIEF_DATA = os.path.join(WORKSPACE, "daily-brief", "data.json")
CRON_JOBS_FILE = os.path.expanduser("~/.openclaw/cron/jobs.json")
CONFIG_FILE = os.path.expanduser("~/.openclaw/mission-control-config.json")

HISTORY_MAX = 20
TAILSCALE_IP = "100.108.159.44"


def now_iso():
    return datetime.now(timezone.utc).isoformat()


def read_json(path):
    try:
        with open(path, "r") as f:
            return json.load(f)
    except Exception:
        return None


def get_hostname():
    try:
        return socket.gethostname()
    except Exception:
        return "unknown"


def get_uptime():
    """Returns uptime in seconds and boot time as ISO string."""
    try:
        with open("/proc/uptime") as f:
            uptime_seconds = float(f.read().split()[0])
        boot_ts = time.time() - uptime_seconds
        boot_iso = datetime.fromtimestamp(boot_ts, tz=timezone.utc).isoformat()
        return uptime_seconds, boot_iso
    except Exception:
        return 0, None


def get_load():
    """Returns load averages (1, 5, 15 min)."""
    try:
        with open("/proc/loadavg") as f:
            parts = f.read().split()
        return float(parts[0]), float(parts[1]), float(parts[2])
    except Exception:
        return 0.0, 0.0, 0.0


def get_memory():
    """Returns ram_total_mb, ram_used_mb, ram_available_mb."""
    try:
        mem = {}
        with open("/proc/meminfo") as f:
            for line in f:
                parts = line.split()
                if len(parts) >= 2:
                    mem[parts[0].rstrip(":")] = int(parts[1])

        total_kb = mem.get("MemTotal", 0)
        available_kb = mem.get("MemAvailable", 0)
        free_kb = mem.get("MemFree", 0)
        buffers_kb = mem.get("Buffers", 0)
        cached_kb = mem.get("Cached", 0)

        total_mb = total_kb / 1024
        available_mb = available_kb / 1024
        used_mb = total_mb - available_mb

        return total_mb, used_mb, available_mb
    except Exception:
        return 0, 0, 0


def get_disk(path="/"):
    """Returns disk total_gb, used_gb, free_gb, pct for given path."""
    try:
        st = os.statvfs(path)
        total = st.f_blocks * st.f_frsize
        free = st.f_bfree * st.f_frsize
        available = st.f_bavail * st.f_frsize
        used = total - free

        total_gb = total / (1024 ** 3)
        used_gb = used / (1024 ** 3)
        free_gb = available / (1024 ** 3)
        pct = round((used / total) * 100) if total > 0 else 0

        return total_gb, used_gb, free_gb, pct
    except Exception:
        return 0, 0, 0, 0


def get_daily_brief():
    """Reads daily-brief/data.json and extracts section counts + tryadd articles."""
    data = read_json(DAILY_BRIEF_DATA)
    if not data:
        return {"last_updated": None, "article_counts": {}, "total_articles": 0, "tryadd_latest": []}

    last_updated = data.get("fetched_at")
    sections = data.get("sections", {})

    article_counts = {}
    total = 0
    tryadd_latest = []

    for section_title, articles in sections.items():
        if not isinstance(articles, list):
            continue
        article_counts[section_title] = len(articles)
        total += len(articles)

        if "tryadd" in section_title.lower():
            for a in articles[:3]:
                tryadd_latest.append({
                    "title": a.get("title", ""),
                    "link": a.get("link", ""),
                    "_source": a.get("_source", a.get("source", ""))
                })

    return {
        "last_updated": last_updated,
        "article_counts": article_counts,
        "total_articles": total,
        "tryadd_latest": tryadd_latest
    }


def get_cron_jobs():
    """Reads ~/.openclaw/cron/jobs.json and extracts job info."""
    data = read_json(CRON_JOBS_FILE)
    if not data:
        return []

    jobs_raw = data.get("jobs", [])
    result = []

    for job in jobs_raw:
        name = job.get("name", "Unknown")
        enabled = job.get("enabled", True)

        schedule_obj = job.get("schedule", {})
        schedule_kind = schedule_obj.get("kind", "")
        if schedule_kind == "cron":
            schedule = schedule_obj.get("expr", "")
        elif schedule_kind == "once":
            schedule = "once"
        else:
            schedule = schedule_kind or "unknown"

        # Next run
        state = job.get("state", {})
        next_run_ms = state.get("nextRunAtMs")
        next_run = None
        if next_run_ms:
            try:
                next_run = datetime.fromtimestamp(next_run_ms / 1000, tz=timezone.utc).isoformat()
            except Exception:
                pass

        # Last run — not in jobs.json directly, skip for now
        last_run = state.get("lastRunAt") or state.get("lastRunAtMs")
        if isinstance(last_run, (int, float)) and last_run > 1e9:
            try:
                last_run = datetime.fromtimestamp(last_run / 1000, tz=timezone.utc).isoformat()
            except Exception:
                last_run = None

        result.append({
            "name": name,
            "schedule": schedule,
            "next_run": next_run,
            "last_run": last_run,
            "enabled": enabled
        })

    return result


def load_history():
    """Loads existing metrics.json and extracts history arrays."""
    existing = read_json(METRICS_FILE)
    if not existing:
        return {"load_1": [], "ram_used_pct": []}
    return existing.get("history", {"load_1": [], "ram_used_pct": []})


def update_history(history, load_1, ram_total_mb, ram_used_mb):
    """Appends current values and trims to HISTORY_MAX."""
    load_hist = history.get("load_1", [])
    ram_hist = history.get("ram_used_pct", [])

    load_hist.append(round(load_1, 2))
    ram_pct = round((ram_used_mb / ram_total_mb) * 100, 1) if ram_total_mb > 0 else 0
    ram_hist.append(ram_pct)

    # Keep last N readings
    load_hist = load_hist[-HISTORY_MAX:]
    ram_hist = ram_hist[-HISTORY_MAX:]

    return {"load_1": load_hist, "ram_used_pct": ram_hist}


def get_roborto_status():
    """
    Infer Roborto's last seen / status from available signals.
    We set 'now' as last_seen when the pusher runs (it's run by cron which is triggered by Roborto's session).
    """
    return {
        "last_seen": now_iso(),
        "model": "anthropic/claude-sonnet-4-6",
        "status": "online"
    }


def push_to_gist(metrics, gist_id, github_token):
    """Pushes metrics.json content to a GitHub Gist."""
    url = f"https://api.github.com/gists/{gist_id}"
    payload = {
        "files": {
            "metrics.json": {
                "content": json.dumps(metrics, indent=2)
            }
        }
    }
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url, data=data, method="PATCH")
    req.add_header("Authorization", f"token {github_token}")
    req.add_header("Content-Type", "application/json")
    req.add_header("Accept", "application/vnd.github.v3+json")
    req.add_header("User-Agent", "Roborto-MissionControl/1.0")

    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            if resp.status == 200:
                print(f"✅ Pushed to GitHub Gist: {gist_id}")
            else:
                print(f"⚠️  Gist push returned status {resp.status}")
    except urllib.error.HTTPError as e:
        print(f"⚠️  Gist push failed: HTTP {e.code} {e.reason}")
    except Exception as e:
        print(f"⚠️  Gist push error: {e}")


def main():
    print("🚀 Mission Control Metrics Pusher starting...")

    # System metrics
    uptime_seconds, boot_time = get_uptime()
    load_1, load_5, load_15 = get_load()
    ram_total_mb, ram_used_mb, ram_available_mb = get_memory()
    disk_total_gb, disk_used_gb, disk_free_gb, disk_pct = get_disk("/")

    machine = {
        "hostname": get_hostname(),
        "uptime_seconds": round(uptime_seconds),
        "boot_time": boot_time,
        "load_1": round(load_1, 2),
        "load_5": round(load_5, 2),
        "load_15": round(load_15, 2),
        "ram_total_mb": round(ram_total_mb),
        "ram_used_mb": round(ram_used_mb),
        "ram_available_mb": round(ram_available_mb),
        "disk_total_gb": round(disk_total_gb, 1),
        "disk_used_gb": round(disk_used_gb, 1),
        "disk_free_gb": round(disk_free_gb, 1),
        "disk_pct": disk_pct,
        "tailscale_ip": TAILSCALE_IP
    }

    # History
    history = load_history()
    history = update_history(history, load_1, ram_total_mb, ram_used_mb)

    # Roborto status
    roborto = get_roborto_status()

    # Daily brief
    brief = get_daily_brief()

    # Cron jobs
    cron_jobs = get_cron_jobs()

    # Build metrics object
    metrics = {
        "updated_at": now_iso(),
        "machine": machine,
        "roborto": roborto,
        "brief": brief,
        "cron_jobs": cron_jobs,
        "history": history
    }

    # Write to file
    os.makedirs(MISSION_CONTROL_DIR, exist_ok=True)
    with open(METRICS_FILE, "w") as f:
        json.dump(metrics, f, indent=2)
    print(f"✅ metrics.json written to {METRICS_FILE}")

    # Print summary
    ram_pct = round((ram_used_mb / ram_total_mb) * 100) if ram_total_mb > 0 else 0
    print(f"   📊 Load: {load_1:.2f} | RAM: {ram_pct}% | Disk: {disk_pct}%")
    print(f"   📰 Brief: {brief['total_articles']} articles across {len(brief['article_counts'])} sections")
    print(f"   ⏱️  Cron jobs: {len(cron_jobs)}")

    # Optional Gist push
    config = read_json(CONFIG_FILE)
    if config:
        gist_id = config.get("gist_id")
        github_token = config.get("github_token")
        if gist_id and github_token:
            push_to_gist(metrics, gist_id, github_token)
        else:
            print("ℹ️  Config found but missing gist_id or github_token — skipping Gist push")

    print("✅ Done.")


if __name__ == "__main__":
    main()
