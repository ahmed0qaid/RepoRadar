# RepoRadar AI

Discover rising GitHub repositories before they become crowded, and find contribution opportunities early.

## What this MVP does
- Collects rising repositories from the GitHub REST API.
- Calculates a heuristic `Rising Score` from stars, forks, recency, issues and growth snapshots.
- Stores historical snapshots in `data/history.json`.
- Generates `data/repositories.json` for a static dashboard.
- Publishes a zero-backend dashboard on GitHub Pages.
- Runs automatically with GitHub Actions every 6 hours.

## Zero-cost architecture
- Frontend: static HTML/CSS/JS on GitHub Pages.
- Collector: Python stdlib only, executed by GitHub Actions.
- Data store: JSON files committed to this public repository.
- API: GitHub REST API using the built-in `GITHUB_TOKEN`.

## Local run
```bash
python scripts/collect.py
python -m http.server 8000 -d docs
```
Open http://localhost:8000

## Deploy
1. Create a **public** GitHub repository.
2. Push this project.
3. In Settings > Pages, choose **GitHub Actions** as the source.
4. Run `Collect RepoRadar data` once from Actions.
5. Run `Deploy RepoRadar Pages` or push to `main`.

## Scores
`Rising Score` is intentionally heuristic in v0.1. It rewards:
- recent star growth between snapshots,
- current popularity,
- forks,
- issue activity,
- recent repository creation.

`Opportunity Score` rewards projects with open issues and healthy activity while mildly penalizing very large/crowded repositories.

## Next versions
- v0.2: language/topic filters and repository detail page.
- v0.3: GitHub issue matching by developer skills.
- v0.4: topic-level trend detection.
- v0.5: ML forecasting after enough history is collected.

## License
MIT
