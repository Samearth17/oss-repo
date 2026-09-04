# OSS WATCH

OSS WATCH is a Django-based open-source repository intelligence product for discovering, assessing, comparing, and monitoring security-focused repositories. It combines the transparent evaluation approach from the preceding tool-evaluation work with continuous repository monitoring.

```text
DISCOVER → ASSESS → COMPARE → WATCH → MONITOR → DETECT → PRIORITIZE → ALERT
```

## Product views

- **Overview** — current priority queue, recent signals, discovery status, and Army-focused capability lens.
- **Discover** — live GitHub repository search with pagination, filters, scoring, Army relevance, watchlist actions, and direct GitHub links.
- **Compare** — side-by-side technical and Army relevance comparison for selected repositories.
- **Watchlist** — only repositories explicitly selected for monitoring.
- **Alerts** — previous-versus-current changes for tracked repositories.
- **Army Lens** — capability-oriented exploration of potential Indian Army relevance.
- **Repository Intelligence** — technical score, Army relevance, evidence, activity, history, changes, and GitHub link.
- **System** — monitoring architecture and runtime state.

## Architecture

```text
GitHub API / fixture dataset
            ↓
       Discovery
            ↓
       Assessment
       ┌────┴────┐
       ↓         ↓
Technical    Army relevance
score /40       score /5
       └────┬────┘
            ↓
        Watchlist
            ↓
         Snapshot
            ↓
     Change detection
            ↓
        Priority
            ↓
          Alerts
            ↓
       Django web UI
```

Backend responsibilities are separated across `src/github_client.py` (GitHub REST search and normalization), `src/detector.py` (previous/current comparison), `src/scoring.py` (technical scoring and priority), `src/army_relevance.py` (transparent Army capability assessment), `src/storage.py` (JSON persistence), and `src/dashboard.py` (orchestration). `osswatch/` contains the Django configuration and API views.

## Demo mode — offline

Demo mode uses five deterministic fixture repositories and does not need internet access. The five fixtures are a presentation dataset, not a platform limit.

```bash
python3 -m pip install -r requirements.txt
python3 main.py --demo
```

Open `http://127.0.0.1:8000`.

## Live GitHub discovery

Live mode searches GitHub dynamically, returns 20 repositories per page by default, scores results on the server, assesses Army relevance, and lets users add any result to the persisted monitoring watchlist.

```bash
export GITHUB_TOKEN="github_pat_..."
python3 main.py
```

`GITHUB_TOKEN` is optional for public API access but recommended for higher API limits. It is read only by the Python backend, is never exposed to the browser, and must never be committed.

The Discover page keeps dynamic search results separate from the persistent Watchlist. A repository can be viewed and assessed before it is added to monitoring.

## Demo change-detection procedure

1. Run `python3 main.py --demo` to create a baseline snapshot.
2. Change a fixture value such as `wazuh/wazuh` `stars: 15080` to `stars: 15200`.
3. Run the scan again or click **Run scan**.
4. Open **Alerts** and inspect the generated `STAR_CHANGE`, previous value, current value, and delta.

Score and priority events are generated only when backend-computed assessment inputs actually change. No activity history is fabricated.

## Technical scoring

The technical evaluation remains a transparent 8-criterion model with a maximum of 40:

1. Security Functionality
2. Detection Capability
3. Activity / Maintenance
4. Community Adoption
5. Documentation
6. Deployment Practicality
7. Open-Source Health
8. Defence Relevance

Priority thresholds are HIGH 36–40, MEDIUM 28–35, LOW 20–27, and REVIEW below 20.

Live repository metadata drives activity, adoption, documentation, and open-source-health signals. Security-specific dimensions use structured rubric values where available, with conservative metadata-based fallbacks.

## Indian Army relevance

Army relevance is deliberately separate from the 40-point technical score. It is a 1–5 capability-alignment assessment with broad areas such as:

- Cyber Defence
- Network Security
- Threat Detection
- Security Monitoring
- Incident Response
- Digital Forensics
- Infrastructure Security
- Data / Intelligence Analysis

The result is a high-level prioritization aid for further technical evaluation, not an operational recommendation.

## Tests

```bash
pytest -q
```

Tests cover repository normalization, GitHub search pagination, dynamic watchlist additions, repository change detection, technical scoring and thresholds, Army relevance classification, and JSON persistence.

## Limitations

OSS WATCH is a repository-level discovery, assessment, prioritization, and metadata-monitoring prototype. It does not perform vulnerability analysis, exploit detection, contributor sentiment analysis, threat intelligence, or machine-learning predictions. Demo mode uses fixtures; live mode depends on GitHub availability and API limits.

### Force a monitoring scan

```bash
python3 main.py --scan
```

Live mode does not scan tracked repositories automatically at server startup unless `--scan` is supplied. Demo mode performs its fixture scan automatically.

## Render deployment

Build command:

```bash
pip install -r requirements.txt
```

Start command:

```bash
gunicorn --bind 0.0.0.0:$PORT osswatch.wsgi:application
```

Set these Render environment variables:

- `DJANGO_SECRET_KEY`
- `GITHUB_TOKEN`
- `ALLOWED_HOSTS` (include the Render hostname if needed)
