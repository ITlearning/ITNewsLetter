# IT NewsLetter - Discord Aggregator

This repository collects multiple tech feeds and sends new items to a Discord channel via webhook.

## Phase 1 (implemented)
- Feed source management via `config/sources.yaml`
- Scheduled collection using GitHub Actions
- Duplicate prevention via `data/state.json`
- Delivery to Discord webhook
- Run summary in `data/last_run.json`
- Archive data in `data/news.json`
- Curation-oriented archive site with today's picks, detail pages, and related articles

## Project Structure
- `config/sources.yaml`: feed sources
- `config/taxonomy.yaml`: shared taxonomy + source overlays
- `config/taxonomy_examples.yaml`: representative examples for taxonomy tuning
- `config/lazy_detail_allowlist.json`: on-demand detail briefing allowlist for legacy English items
- `scripts/fetch_and_send.py`: fetch, dedupe, send logic
- `scripts/build_archive_site.py`: build static archive payload and detail pages for GitHub Pages
- `api/`: Vercel Functions for on-demand legacy detail briefings
- `site/`: archive website source
- `data/state.json`: previously sent IDs
- `data/news.json`: archived sent items
- `data/last_run.json`: run summary
- `.github/workflows/news-discord.yml`: scheduled automation
- `.github/workflows/news-archive-pages.yml`: GitHub Pages deployment

## Setup
1. Push this repository to GitHub.
2. In repository settings, add secret:
   - `DISCORD_WEBHOOK_URL`
   - `OPENAI_API_KEY` (for English title translation + list/detail summaries)
3. Enable GitHub Actions.
4. Run `Newsletter Discord Sync` once with `workflow_dispatch` (first bootstrap).
5. Scheduler runs every 4 hours (at minute `:13`) and automatically sends 5-7 new items per run depending on Discord message length.
6. Optional fallback: set `chain=true` on manual run to keep 4-hour self-dispatch loop.
7. To enable/disable fallback globally, set repository variable `SELF_DISPATCH_ENABLED=true|false`.
8. Manual runs can temporarily override the per-run range with `min_items_per_run` and `max_items_per_run`.
9. Priority selection uses a shared 4-slot taxonomy across all sources and a GeekNews-specific overlay.
10. To publish the archive site, set GitHub Pages source to `GitHub Actions`.
11. Optional: add repository variable `LAZY_DETAIL_API_URL` after deploying the Vercel lazy-detail API.

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
- `MIN_NEW_ITEMS_PER_RUN` (default: `5`)
- `MAX_NEW_ITEMS_PER_RUN` (default: `7`)
- `MAX_ITEM_AGE_DAYS` (default: `3`, items older than this are skipped)
- `TECH_PRIORITY_QUOTA` (default: `3`, workflow currently sets `3`; applies to `practical_tech + tools_agents`)
- `GEEKNEWS_MAX_PER_RUN` (default: `3`, workflow currently sets `3`)
- `DISCORD_RETRY` (default: `3`)
- `REQUEST_TIMEOUT_SEC` (default: `15`)
- `SEND_DELAY_SEC` (default: `0.6`)
- `DISCORD_BATCH_MAX_CHARS` (default: `1900`, selected items are sent in one batched message)
- `DISCORD_MENTION` (default: empty)
- `DISCORD_USER_AGENT` (default: browser-like UA string)
- `OPENAI_MODEL` (default: `gpt-4.1-mini-2025-04-14`)
- `OPENAI_FALLBACK_MODELS` (default: `gpt-4.1-mini,gpt-4.1-nano-2025-04-14,gpt-4.1-nano,gpt-4o-mini-2024-07-18,gpt-4o-mini`)
- `OPENAI_TIMEOUT_SEC` (default: `20`)

## Lazy Detail API (legacy English archive items)
- New English items still generate `translated_title`, `short_summary`, and `detailed_summary` at dispatch time.
- Older English archive items can lazily generate a richer `detailed_summary` on the detail page.
- Korean items and GeekNews are excluded from lazy generation.
- Supported legacy sources are controlled by `config/lazy_detail_allowlist.json`.
- HN RSS lazy detail support is limited to curated downstream domains, not the whole HN source.
- The archive detail page never stores or mirrors original article bodies. The API only stores generated `detailed_summary` in Redis.
- Lazy-detail Redis cache keys now use the `lazy-detail:v2:*` namespace, so older cached briefings are ignored automatically after deploy.

### Refreshing legacy briefings
Run a dry run first:

```bash
python3 scripts/reset_legacy_briefings.py
```

Apply the cleanup only after reviewing the sample output:

```bash
python3 scripts/reset_legacy_briefings.py --apply
```

What it does:
- Clears only legacy plain-text `detailed_summary` values.
- Preserves entries that already look like the new limited Markdown format.
- Touches only items that can lazily regenerate a new briefing under the current allowlist policy.

### Vercel setup
Deploy this repository to Vercel and configure:
- `ARCHIVE_DATA_URL`
  - Example: `https://itlearning.github.io/ITNewsLetter/data/news-archive.json`
- `OPENAI_API_KEY`
- `OPENAI_MODEL` (optional, defaults to `gpt-4.1-mini-2025-04-14`)
- `OPENAI_FALLBACK_MODELS` (optional)
- `UPSTASH_REDIS_REST_URL`
- `UPSTASH_REDIS_REST_TOKEN`

Then set GitHub repository variable:
- `LAZY_DETAIL_API_URL`
  - Example: `https://your-project.vercel.app/api/lazy-detail`

## Notes
- Some newsletters do not expose RSS/Atom feeds directly.
- Add only verified feed URLs to `config/sources.yaml`.
- `source_type: sitemap` + `path_prefix` can be used for sites without RSS (e.g., Anthropic engineering posts).
- New item selection uses a shared 4-slot taxonomy: `practical_tech`, `tools_agents`, `strategy_insight`, `industry_business`.
- GeekNews has source-specific overlay terms and a dynamic cap: up to 2 items in a 5-item batch, up to 3 items in a 6-7 item batch.
- HN now uses the official Hacker News API, keeps a stronger source prior, and enriches stories with HN-native context so technical posts and engineering essays surface more often.
- Product Hunt Feed is currently disabled by default because signal quality was low for the Discord batch.
- GeekNews posts include a short 3-4 line preview from feed summary when AI summary is not used.
- English items can store `translated_title`, `short_summary`, and `detailed_summary` at dispatch time.
- Korean and GeekNews items do not trigger extra detail-page GPT calls.
- Older allowlisted English articles can request a richer detail briefing on demand through the Vercel API.
- Older HN items with a stored HN story id can request richer detail briefings from HN story/comment context without crawling the downstream article body.
- Multiple selected items are grouped into a single Discord push per run (subject to message size limit).
- Batch size is selected automatically within the configured min/max range, shrinking from max to min when the Discord message gets too long.
- Selection logs now include the winning taxonomy slot and matched terms for explainability.
- Items older than 3 days are skipped by default before prioritization.
- The archive site is built from `data/news.json`, enriches older items with taxonomy metadata during the Pages build, and generates static detail pages under `dist/news/<detail-slug>/`.
- Archive detail pages are briefing pages, not mirrored article pages: the site stores metadata, summaries, and original links, but does not mirror full article bodies.
- The list page now highlights the latest sent batch in a dedicated today's curation section.
