# IT NewsLetter - Discord Aggregator

This repository collects multiple tech feeds and sends new items to a Discord channel via webhook.

## Phase 1 (implemented)
- Feed source management via `config/sources.yaml`
- Scheduled collection using GitHub Actions
- Duplicate prevention via `data/state.json`
- Delivery to Discord webhook
- Run summary in `data/last_run.json`
- Archive data in `data/news.json`

## Project Structure
- `config/sources.yaml`: feed sources
- `scripts/fetch_and_send.py`: fetch, dedupe, send logic
- `data/state.json`: previously sent IDs
- `data/news.json`: archived sent items
- `data/last_run.json`: run summary
- `.github/workflows/news-discord.yml`: scheduled automation

## Setup
1. Push this repository to GitHub.
2. In repository settings, add secret:
   - `DISCORD_WEBHOOK_URL`
   - `OPENAI_API_KEY` (for title translation + short summary)
3. Enable GitHub Actions.
4. Run `Newsletter Discord Sync` once with `workflow_dispatch` (first bootstrap).
5. Scheduler runs every 90 minutes and sends up to 5 new items per run.
6. Optional fallback: set `chain=true` on manual run to keep 90-minute self-dispatch loop.
7. To enable/disable fallback globally, set repository variable `SELF_DISPATCH_ENABLED=true|false`.
8. Priority selection: fill GeekNews first (up to 3), then fill remaining by technical/general priority.

## Local Dry Run
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
DRY_RUN=1 python scripts/fetch_and_send.py
```

## Environment Variables (optional)
- `STATE_TTL_DAYS` (default: `14`)
- `MAX_STATE_IDS` (default: `3000`)
- `MAX_NEWS_ITEMS` (default: `2000`)
- `MAX_NEW_ITEMS_PER_RUN` (default: `3`, workflow currently sets `5`)
- `MAX_ITEM_AGE_DAYS` (default: `3`, items older than this are skipped)
- `TECH_PRIORITY_QUOTA` (default: `2`)
- `GEEKNEWS_MAX_PER_RUN` (default: `1`, workflow currently sets `3`)
- `DISCORD_RETRY` (default: `3`)
- `REQUEST_TIMEOUT_SEC` (default: `15`)
- `SEND_DELAY_SEC` (default: `0.6`)
- `DISCORD_MENTION` (default: empty)
- `DISCORD_USER_AGENT` (default: browser-like UA string)
- `OPENAI_MODEL` (default: `gpt-4.1-mini-2025-04-14`)
- `OPENAI_FALLBACK_MODELS` (default: `gpt-4.1-mini,gpt-4.1-nano-2025-04-14,gpt-4.1-nano,gpt-4o-mini-2024-07-18,gpt-4o-mini`)
- `OPENAI_TIMEOUT_SEC` (default: `20`)

## Notes
- Some newsletters do not expose RSS/Atom feeds directly.
- Add only verified feed URLs to `config/sources.yaml`.
- `source_type: sitemap` + `path_prefix` can be used for sites without RSS (e.g., Anthropic engineering posts).
- New item selection is priority-based: technical/dev-use-case posts first, then general industry news.
- GeekNews has a per-run cap to keep source diversity; remaining slots are filled by technical/general priority.
- Items older than 3 days are skipped by default before prioritization.
