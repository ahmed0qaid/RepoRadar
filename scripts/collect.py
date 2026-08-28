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
ISSUES_FILE = DATA_DIR / "issues.json"
DOCS_ISSUES_FILE = DOCS_DATA_DIR / "issues.json"

TOKEN = os.getenv("GITHUB_TOKEN", "").strip()
API = "https://api.github.com"
VERSION = "0.3"


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
            candidates.append((abs((ts - target).total_seconds()), snapshot))
    if not candidates:
        return None
    candidates.sort(key=lambda item: item[0])
    distance, selected = candidates[0]
    slack = max_slack_hours if max_slack_hours is not None else max(4, hours_ago * 0.45)
    return selected if distance <= slack * 3600 else None


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
    return viral, viral, opportunity


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


def issue_score(issue):
    labels = [label.get("name", "").lower() for label in issue.get("labels", [])]
    score = 38.0
    if any("good first issue" in label for label in labels):
        score += 28
    if any("help wanted" in label for label in labels):
        score += 18
    if any(word in label for label in labels for word in ("beginner", "easy", "starter")):
        score += 10
    if any(word in label for label in labels for word in ("documentation", "docs")):
        score += 5
    score -= min(20, issue.get("comments", 0) * 2.5)
    score -= min(12, len(issue.get("assignees", [])) * 6)
    try:
        updated_days = max(0, (datetime.now(timezone.utc) - parse_ts(issue["updated_at"])).days)
        score += max(0, 10 - updated_days)
    except Exception:
        pass
    return round(clamp(score), 1)


def infer_difficulty(labels, comments):
    text = " ".join(labels).lower()
    if any(x in text for x in ("good first issue", "beginner", "easy", "starter")):
        return "Beginner"
    if any(x in text for x in ("complex", "advanced", "hard")):
        return "Advanced"
    if comments >= 8:
        return "Competitive"
    return "Intermediate"


def collect_issues(repositories):
    """Collect a compact public issue dataset for zero-cost browser matching."""
    output = []
    # Prioritize repos where contribution is plausible; cap calls to protect rate limit.
    candidates = sorted(
        repositories,
        key=lambda r: (r["opportunity_score"], r["viral_score"]),
        reverse=True,
    )[:40]
    for repo in candidates:
        if repo["open_issues"] <= 0:
            continue
        try:
            items = gh_get(f"/repos/{repo['full_name']}/issues", {
                "state": "open",
                "sort": "updated",
                "direction": "desc",
                "per_page": 15,
            })
        except Exception as exc:
            print(f"Issue fetch failed for {repo['full_name']}: {exc}")
            continue
        for issue in items:
            if "pull_request" in issue:
                continue
            labels = [label.get("name", "") for label in issue.get("labels", []) if label.get("name")]
            body = (issue.get("body") or "").replace("\r", " ").replace("\n", " ").strip()
            body = " ".join(body.split())[:280]
            output.append({
                "id": issue.get("id"),
                "number": issue.get("number"),
                "title": issue.get("title", "Untitled issue"),
                "url": issue.get("html_url"),
                "repository": repo["full_name"],
                "repo_url": repo["url"],
                "language": repo["language"],
                "topics": repo.get("topics", []),
                "labels": labels,
                "comments": issue.get("comments", 0),
                "assignees": len(issue.get("assignees", [])),
                "created_at": issue.get("created_at"),
                "updated_at": issue.get("updated_at"),
                "body_excerpt": body,
                "difficulty": infer_difficulty(labels, issue.get("comments", 0)),
                "issue_opportunity_score": issue_score(issue),
                "repo_opportunity_score": repo["opportunity_score"],
                "repo_viral_score": repo["viral_score"],
            })
        time.sleep(0.25)

    output.sort(
        key=lambda i: (i["issue_opportunity_score"], i["repo_opportunity_score"], i["repo_viral_score"]),
        reverse=True,
    )
    return output[:400]


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

    contribution_issues = collect_issues(repos)
    issue_payload = {
        "version": VERSION,
        "generated_at": now,
        "count": len(contribution_issues),
        "issues": contribution_issues,
    }

    OUTPUT_FILE.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    DOCS_OUTPUT_FILE.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    ISSUES_FILE.write_text(json.dumps(issue_payload, indent=2, ensure_ascii=False), encoding="utf-8")
    DOCS_ISSUES_FILE.write_text(json.dumps(issue_payload, indent=2, ensure_ascii=False), encoding="utf-8")

    history.setdefault("snapshots", []).append({"timestamp": now, "repos": snapshot_repos})
    history["snapshots"] = history["snapshots"][-240:]
    HISTORY_FILE.write_text(json.dumps(history, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"RepoRadar v{VERSION}: {len(repos)} repos, {len(contribution_issues)} contribution issues")


if __name__ == "__main__":
    main()
