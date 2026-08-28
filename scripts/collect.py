#!/usr/bin/env python3
import json
import math
import os
import time
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data"
DOCS_DATA_DIR = ROOT / "docs" / "data"
HISTORY_FILE = DATA_DIR / "history.json"
OUTPUT_FILE = DATA_DIR / "repositories.json"
DOCS_OUTPUT_FILE = DOCS_DATA_DIR / "repositories.json"

TOKEN = os.getenv("GITHUB_TOKEN", "").strip()
API = "https://api.github.com"
VERSION = "0.2"


def gh_get(path, params=None):
    url = API + path
    if params:
        url += "?" + urllib.parse.urlencode(params)
    headers = {
        "Accept": "application/vnd.github+json",
        "User-Agent": f"RepoRadar-AI/{VERSION}",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    if TOKEN:
        headers["Authorization"] = f"Bearer {TOKEN}"
    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req, timeout=30) as res:
        return json.loads(res.read().decode("utf-8"))


def load_history():
    if HISTORY_FILE.exists():
        try:
            data = json.loads(HISTORY_FILE.read_text(encoding="utf-8"))
            if isinstance(data, dict) and isinstance(data.get("snapshots"), list):
                return data
        except Exception:
            pass
    return {"snapshots": []}


def clamp(value, lo=0, hi=100):
    return max(lo, min(hi, value))


def parse_ts(value):
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def snapshot_near(history, hours_ago, max_slack_hours=None):
    """Return the closest snapshot at-or-before the requested age.

    The collector runs every six hours, so a little slack keeps calculations
    useful when Actions starts a few minutes late.
    """
    snapshots = history.get("snapshots", [])
    if not snapshots:
        return None
    now = datetime.now(timezone.utc)
    target = now - timedelta(hours=hours_ago)
    candidates = []
    for snapshot in snapshots:
        try:
            ts = parse_ts(snapshot["timestamp"])
        except Exception:
            continue
        if ts <= now:
            candidates.append((abs((ts - target).total_seconds()), ts, snapshot))
    if not candidates:
        return None
    candidates.sort(key=lambda item: item[0])
    distance, _, selected = candidates[0]
    slack = max_slack_hours if max_slack_hours is not None else max(4, hours_ago * 0.45)
    if distance > slack * 3600:
        return None
    return selected


def stars_from(snapshot, full_name, fallback):
    if not snapshot:
        return fallback
    return snapshot.get("repos", {}).get(full_name, {}).get("stars", fallback)


def growth_metrics(repo, history):
    name = repo["full_name"]
    stars = repo.get("stargazers_count", 0)
    s6 = snapshot_near(history, 6, 4)
    s12 = snapshot_near(history, 12, 5)
    s24 = snapshot_near(history, 24, 8)
    s7d = snapshot_near(history, 168, 36)

    stars6 = stars_from(s6, name, stars)
    stars12 = stars_from(s12, name, stars6)
    stars24 = stars_from(s24, name, stars)
    stars7d = stars_from(s7d, name, stars)

    delta6 = max(0, stars - stars6) if s6 else 0
    delta24 = max(0, stars - stars24) if s24 else 0
    delta7d = max(0, stars - stars7d) if s7d else 0

    velocity6 = delta6 / 6 if s6 else 0.0
    velocity24 = delta24 / 24 if s24 else velocity6
    previous_velocity6 = max(0, stars6 - stars12) / 6 if s6 and s12 else velocity6
    acceleration = (velocity6 - previous_velocity6) / 6 if s6 and s12 else 0.0

    base24 = max(1, stars24) if s24 else max(1, stars)
    base7d = max(1, stars7d) if s7d else max(1, stars)
    growth24_pct = (delta24 / base24) * 100 if s24 else 0.0
    growth7d_pct = (delta7d / base7d) * 100 if s7d else 0.0

    return {
        "growth_6h": delta6,
        "growth_24h": delta24,
        "growth_7d": delta7d,
        "growth_24h_pct": round(growth24_pct, 2),
        "growth_7d_pct": round(growth7d_pct, 2),
        "star_velocity": round(velocity24, 3),
        "star_velocity_6h": round(velocity6, 3),
        "star_acceleration": round(acceleration, 4),
        "has_6h_history": bool(s6),
        "has_24h_history": bool(s24),
        "has_7d_history": bool(s7d),
    }


def score_repo(repo, metrics):
    stars = repo.get("stargazers_count", 0)
    forks = repo.get("forks_count", 0)
    issues = repo.get("open_issues_count", 0)
    created = parse_ts(repo["created_at"])
    updated = parse_ts(repo["updated_at"])
    now = datetime.now(timezone.utc)
    age_days = max(1, (now - created).days)
    stale_days = max(0, (now - updated).days)

    # Viral score favours momentum over raw popularity.
    velocity = metrics["star_velocity"]
    growth_pct = metrics["growth_24h_pct"]
    acceleration = metrics["star_acceleration"]
    velocity_component = min(32, math.log10(velocity + 1) * 16)
    percent_component = min(24, math.log10(growth_pct + 1) * 14)
    acceleration_component = min(14, max(0, acceleration) * 50)
    popularity_component = min(14, math.log10(stars + 1) * 3.5)
    activity_component = min(10, math.log10(issues + forks + 1) * 3)
    freshness_component = max(0, 6 - min(6, stale_days / 5))
    if not metrics["has_24h_history"]:
        # Cold-start estimate until enough snapshots have accumulated.
        velocity_component = min(25, math.log10((stars / max(1, age_days)) + 1) * 12)
        percent_component = min(18, (30 / max(30, age_days)) * 18)

    viral = round(clamp(
        velocity_component + percent_component + acceleration_component +
        popularity_component + activity_component + freshness_component
    ), 1)

    issue_signal = min(32, math.log10(issues + 1) * 11)
    freshness = max(0, 22 - min(22, stale_days * 1.2))
    contributor_room = max(0, 25 - min(25, math.log10(stars + 1) * 4.5))
    momentum_bonus = min(16, viral * 0.16)
    fork_signal = min(8, math.log10(forks + 1) * 2.7)
    opportunity = round(clamp(issue_signal + freshness + contributor_room + momentum_bonus + fork_signal), 1)

    # Keep the old name as an alias so existing clients do not break.
    rising = viral
    return rising, viral, opportunity


def classify(repo):
    stars = repo["stars"]
    viral = repo["viral_score"]
    opportunity = repo["opportunity_score"]
    growth24 = repo["growth_24h"]
    growth_pct = repo["growth_24h_pct"]

    categories = []
    if viral >= 72 or (stars >= 1000 and growth24 >= 100):
        categories.append("trending_now")
    if viral >= 58 and (growth_pct >= 8 or repo["star_acceleration"] > 0.08):
        categories.append("rising_fast")
    if stars <= 1500 and viral >= 48:
        categories.append("hidden_gem")
    if opportunity >= 62 and repo["open_issues"] > 0:
        categories.append("best_to_contribute")
    if not categories:
        categories.append("watchlist")
    return categories


def main():
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    DOCS_DATA_DIR.mkdir(parents=True, exist_ok=True)
    history = load_history()

    since = (datetime.now(timezone.utc) - timedelta(days=180)).date().isoformat()
    queries = [
        f"created:>{since} stars:>25",
        f"created:>{since} stars:>80 topic:ai",
        f"created:>{since} stars:>40 topic:developer-tools",
        f"created:>{since} stars:>40 topic:machine-learning",
        f"created:>{since} stars:>40 topic:cli",
    ]

    merged = {}
    for query in queries:
        data = gh_get("/search/repositories", {
            "q": query,
            "sort": "updated",
            "order": "desc",
            "per_page": 60,
        })
        for item in data.get("items", []):
            if item.get("archived") or item.get("fork"):
                continue
            merged[item["full_name"]] = item
        time.sleep(0.7)

    repos = []
    snapshot_repos = {}
    for repo in merged.values():
        metrics = growth_metrics(repo, history)
        rising, viral, opportunity = score_repo(repo, metrics)
        snapshot_repos[repo["full_name"]] = {
            "stars": repo.get("stargazers_count", 0),
            "forks": repo.get("forks_count", 0),
            "open_issues": repo.get("open_issues_count", 0),
        }
        row = {
            "name": repo["name"],
            "full_name": repo["full_name"],
            "url": repo["html_url"],
            "description": repo.get("description") or "No description provided.",
            "language": repo.get("language") or "Other",
            "stars": repo.get("stargazers_count", 0),
            "forks": repo.get("forks_count", 0),
            "open_issues": repo.get("open_issues_count", 0),
            "created_at": repo.get("created_at"),
            "updated_at": repo.get("updated_at"),
            "topics": repo.get("topics", []),
            "rising_score": rising,
            "viral_score": viral,
            "opportunity_score": opportunity,
            **metrics,
        }
        # Compatibility with v0.1 UI/data consumers.
        row["star_delta"] = row["growth_6h"] or row["growth_24h"]
        row["categories"] = classify(row)
        repos.append(row)

    repos.sort(key=lambda r: (r["viral_score"], r["opportunity_score"], r["stars"]), reverse=True)
    repos = repos[:150]
    now = datetime.now(timezone.utc).isoformat()
    category_counts = {
        key: sum(key in repo["categories"] for repo in repos)
        for key in ["trending_now", "rising_fast", "hidden_gem", "best_to_contribute", "watchlist"]
    }
    payload = {
        "version": VERSION,
        "generated_at": now,
        "count": len(repos),
        "signals": category_counts,
        "repositories": repos,
    }

    OUTPUT_FILE.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    DOCS_OUTPUT_FILE.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")

    history.setdefault("snapshots", []).append({"timestamp": now, "repos": snapshot_repos})
    # 240 snapshots = roughly 60 days at a six-hour cadence.
    history["snapshots"] = history["snapshots"][-240:]
    HISTORY_FILE.write_text(json.dumps(history, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"RepoRadar v{VERSION}: collected {len(repos)} repositories")


if __name__ == "__main__":
    main()
