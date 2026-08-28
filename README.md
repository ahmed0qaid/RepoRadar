# RepoRadar AI

Discover rising GitHub repositories before they become crowded — then find the best open issues for your skills.

## Current release: v0.3.0

RepoRadar is a zero-paid-infrastructure open-source intelligence dashboard built on GitHub Actions + GitHub Pages.

### v0.2 — Trend intelligence
- Real growth windows: 6h, 24h and 7d.
- Star velocity and acceleration.
- `Viral Score` focused on momentum, not only raw stars.
- `Opportunity Score` for contributor-friendly repositories.
- Automatic repository signals:
  - 🔥 Trending Now
  - 🚀 Rising Fast
  - 💎 Hidden Gems
  - 🎯 Best to Contribute
- Historical snapshots retained for roughly 60 days at the default six-hour cadence.

### v0.3 — Contribution matcher
- Collects a compact dataset of public open GitHub issues from high-opportunity repositories.
- Scores issues using `good first issue`, `help wanted`, activity, comments and assignees.
- Browser-side skill matching — no account required.
- Skill aliases support Python/backend/AI, TypeScript/web, Flutter/mobile, docs, Docker, cloud and database terms.
- User skills are stored only in browser `localStorage`.
- No OpenAI API or other paid AI service is required.

## Zero-cost architecture

```text
GitHub REST API
      ↓
GitHub Actions (every 6 hours)
      ↓
Python collector (stdlib only)
      ↓
repositories.json + issues.json + history.json
      ↓
GitHub Pages static dashboard
      ↓
Local browser skill matcher
```

- Frontend: static HTML/CSS/JS.
- Collector: Python standard library only.
- Data store: JSON committed to the repository.
- Authentication: built-in `GITHUB_TOKEN` inside Actions.
- Hosting: GitHub Pages.
- Paid APIs: none.

## Scoring model

`Viral Score` combines recent star velocity, percentage growth, acceleration, current popularity, repository activity and freshness. During the first day, RepoRadar uses a cold-start estimate until enough snapshots exist.

`Opportunity Score` rewards open-issue activity, freshness, contributor room, momentum and fork activity while reducing the advantage of extremely crowded repositories.

Issue matching combines developer skills with issue title/body/labels, repository language/topics, issue labels and competition signals. It is heuristic by design in v0.3 and remains fully local/free.

## Data lifecycle

The collector runs at `17 */6 * * *` and can also be started manually. It validates Python syntax and generated JSON before committing refreshed data. The first run creates the initial snapshot; true 6h/24h/7d growth measurements become available as history accumulates.

## Local run

```bash
python scripts/collect.py
python -m http.server 8000 -d docs
```

Then open `http://localhost:8000`.

For authenticated collection locally, expose a GitHub token as `GITHUB_TOKEN` before running the collector. The hosted GitHub Action automatically uses the repository's built-in token.

## Roadmap
- v0.4: emerging-topic detection and topic velocity.
- v0.5: contribution competition signals from PR/issue lifecycle.
- v0.6: forecasting once enough historical snapshots exist.
- v1.0: personalized open-source opportunity engine.

## License
MIT
