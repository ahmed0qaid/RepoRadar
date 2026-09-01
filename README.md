# RepoRadar AI

Discover rising GitHub repositories before they become crowded — then find high-opportunity open issues that match your skills.

RepoRadar is a **zero-paid-infrastructure open-source intelligence system** built with Python, GitHub Actions, GitHub Pages, and browser-side matching.

## Why this project matters

RepoRadar demonstrates practical engineering across **data collection, scheduled automation, scoring systems, static cloud deployment, local-first personalization, and cost-aware architecture**.

Instead of depending on paid AI APIs or hosted databases, the system runs entirely on GitHub infrastructure and keeps personalization in the browser.

## Current release — v0.3.0

### Trend intelligence

- Real growth windows: 6h, 24h and 7d.
- Star velocity and acceleration.
- `Viral Score` focused on momentum rather than raw popularity.
- `Opportunity Score` for contributor-friendly repositories.
- Automatic repository signals:
  - 🔥 Trending Now
  - 🚀 Rising Fast
  - 💎 Hidden Gems
  - 🎯 Best to Contribute
- Historical snapshots retained for roughly 60 days at the default six-hour cadence.

### Contribution matcher

- Collects a compact dataset of public GitHub issues from high-opportunity repositories.
- Scores issues using `good first issue`, `help wanted`, activity, comments and assignees.
- Matches issues to developer skills directly in the browser.
- Skill aliases cover Python/backend/AI, TypeScript/web, Flutter/mobile, documentation, Docker, cloud and database terms.
- User skills stay in browser `localStorage`.
- No OpenAI API or paid AI service is required.

## Architecture

```text
GitHub REST API
      │
      ▼
GitHub Actions
(scheduled every 6 hours)
      │
      ▼
Python Collector
(stdlib only)
      │
      ├── repositories.json
      ├── issues.json
      └── history.json
      │
      ▼
GitHub Pages
Static Dashboard
      │
      ▼
Browser-side Skill Matcher
(local personalization)
```

## Engineering highlights

- Designed a scheduled data pipeline with GitHub Actions instead of a persistent server.
- Implemented historical snapshots to calculate real repository growth windows.
- Built separate ranking models for momentum and contributor opportunity.
- Added validation of generated JSON before automated commits.
- Kept the collector dependency-free by using the Python standard library only.
- Designed browser-local personalization to avoid storing user profiles on a backend.
- Chose a static deployment architecture to keep infrastructure cost at `$0`.
- Separated collection, scoring, generated datasets, and presentation concerns.

## Tech stack

| Layer | Technology |
| --- | --- |
| Data collection | Python standard library |
| External API | GitHub REST API |
| Automation / CI | GitHub Actions |
| Data persistence | Versioned JSON snapshots |
| Frontend | HTML, CSS, JavaScript |
| Personalization | Browser `localStorage` |
| Hosting | GitHub Pages |
| Paid infrastructure | None |

## Scoring model

`Viral Score` combines recent star velocity, percentage growth, acceleration, current popularity, repository activity and freshness. During cold start, RepoRadar uses an estimate until enough historical snapshots exist.

`Opportunity Score` rewards open-issue activity, freshness, contributor room, momentum and fork activity while reducing the advantage of extremely crowded repositories.

Issue matching combines developer skills with issue title/body/labels, repository language/topics, issue labels and competition signals. The current matcher is heuristic by design and remains fully local/free.

## Data lifecycle

The collector runs at `17 */6 * * *` and can also be triggered manually.

Each collection cycle:

```text
Fetch GitHub data
      ↓
Normalize repositories/issues
      ↓
Update historical snapshots
      ↓
Calculate scores
      ↓
Validate generated JSON
      ↓
Commit refreshed datasets
      ↓
GitHub Pages serves latest data
```

The first run creates the initial snapshot. True 6h/24h/7d measurements become available as history accumulates.

## Local run

```bash
python scripts/collect.py
python -m http.server 8000 -d docs
```

Then open `http://localhost:8000`.

For authenticated local collection, expose a GitHub token as `GITHUB_TOKEN`. The hosted workflow uses the repository-provided token.

## Design decisions

### Why GitHub Actions instead of a backend server?

The workload is periodic rather than request-driven. Scheduled Actions remove server maintenance and keep the project deployable at zero infrastructure cost.

### Why JSON instead of a database?

The dashboard is read-heavy, compact, and generated on a fixed cadence. Versioned JSON makes historical changes inspectable while keeping deployment simple.

### Why browser-side matching?

Skill matching does not require a server round-trip. Keeping the profile locally reduces infrastructure, privacy, and authentication complexity.

## Roadmap

- v0.4: emerging-topic detection and topic velocity.
- v0.5: contribution competition signals from PR/issue lifecycle.
- v0.6: forecasting once enough historical snapshots exist.
- v1.0: personalized open-source opportunity engine.

## Related engineering projects

- [FlowGuard — Agentic Automation Control Plane](https://github.com/ahmed2qaid/agentic-automation-control-plane)
- [TrustFlow Sentinel](https://github.com/ahmed2qaid/trustflow-sentinel)
- [Ahmed Software Engineering Portfolio](https://github.com/ahmed2qaid/ahmed-portfolio)

## License

MIT
