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


def gh_get(path, params=None):
    url = API + path
    if params:
        url += "?" + urllib.parse.urlencode(params)
    headers = {
        "Accept": "application/vnd.github+json",
        "User-Agent": "RepoRadar-AI/0.1",
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
            return json.loads(HISTORY_FILE.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {"snapshots": []}


def clamp(v, lo=0, hi=100):
    return max(lo, min(hi, v))


def score_repo(repo, previous):
    stars = repo.get("stargazers_count", 0)
    forks = repo.get("forks_count", 0)
    issues = repo.get("open_issues_count", 0)
    created = datetime.fromisoformat(repo["created_at"].replace("Z", "+00:00"))
    age_days = max(1, (datetime.now(timezone.utc) - created).days)
    prev_stars = previous.get(repo["full_name"], {}).get("stars", stars)
    star_delta = max(0, stars - prev_stars)

    growth_component = min(45, star_delta * 2.2)
    popularity_component = min(20, math.log10(stars + 1) * 5)
    fork_component = min(12, math.log10(forks + 1) * 4)
    issue_component = min(10, math.log10(issues + 1) * 4)
    recency_component = max(0, 13 - min(13, age_days / 15))
    rising = round(clamp(growth_component + popularity_component + fork_component + issue_component + recency_component), 1)

    crowd_penalty = min(25, math.log10(stars + 1) * 5)
    opportunity = round(clamp(45 + min(25, math.log10(issues + 1) * 8) + min(18, fork_component) + min(12, recency_component) - crowd_penalty), 1)

    return star_delta, rising, opportunity


def main():
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    DOCS_DATA_DIR.mkdir(parents=True, exist_ok=True)
    history = load_history()
    previous = {}
    if history.get("snapshots"):
        previous = history["snapshots"][-1].get("repos", {})

    since = (datetime.now(timezone.utc) - timedelta(days=120)).date().isoformat()
    queries = [
        f"created:>{since} stars:>25",
        f"created:>{since} stars:>100 topic:ai",
        f"created:>{since} stars:>50 topic:developer-tools",
    ]

    merged = {}
    for q in queries:
        data = gh_get("/search/repositories", {
            "q": q,
            "sort": "stars",
            "order": "desc",
            "per_page": 50,
        })
        for item in data.get("items", []):
            if item.get("archived") or item.get("fork"):
                continue
            merged[item["full_name"]] = item
        time.sleep(1)

    repos = []
    snapshot_repos = {}
    for repo in merged.values():
        delta, rising, opportunity = score_repo(repo, previous)
        snapshot_repos[repo["full_name"]] = {"stars": repo.get("stargazers_count", 0)}
        repos.append({
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
            "star_delta": delta,
            "rising_score": rising,
            "opportunity_score": opportunity,
        })

    repos.sort(key=lambda r: (r["rising_score"], r["star_delta"], r["stars"]), reverse=True)
    repos = repos[:100]
    now = datetime.now(timezone.utc).isoformat()
    payload = {"generated_at": now, "count": len(repos), "repositories": repos}

    OUTPUT_FILE.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    DOCS_OUTPUT_FILE.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")

    history.setdefault("snapshots", []).append({"timestamp": now, "repos": snapshot_repos})
    history["snapshots"] = history["snapshots"][-120:]
    HISTORY_FILE.write_text(json.dumps(history, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"Collected {len(repos)} repositories")


if __name__ == "__main__":
    main()
