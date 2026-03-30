# IT NewsLetter - Discord Aggregator

This repository collects multiple tech feeds and sends new items to a Discord channel via webhook.

## Phase 1 (implemented)
- Feed source management via `config/sources.yaml`
- Scheduled collection using one runner at a time (`launchd` on Mac Studio or GitHub Actions)
- Duplicate prevention via `data/state.json`
- Delivery to Discord webhook
- Run summary in `data/last_run.json`
- Archive data in `data/news.json`
- Curation-oriented archive site with today's picks, detail pages, related articles, and static topic pages

## Project Structure
- `config/sources.yaml`: feed sources
- `config/taxonomy.yaml`: shared taxonomy + source overlays
- `config/taxonomy_examples.yaml`: representative examples for taxonomy tuning
- `config/lazy_detail_allowlist.json`: on-demand detail briefing allowlist for legacy English items
- `scripts/fetch_and_send.py`: fetch, dedupe, send logic
- `scripts/build_archive_site.py`: build static archive payload, detail pages, and `/topics/` pages for GitHub Pages
- `scripts/assets/fonts/`: bundled font assets for deterministic static rendering tasks
- `api/`: Vercel Functions for on-demand legacy detail briefings
- `site/`: archive website source
- `data/state.json`: previously sent IDs
- `data/news.json`: archived sent items
- `data/last_run.json`: run summary
- `.github/workflows/news-discord.yml`: manual fallback dispatch only
- `.github/workflows/news-archive-pages.yml`: GitHub Pages deployment

## Setup
1. Push this repository to GitHub.
2. In repository settings, add secret:
   - `DISCORD_WEBHOOK_URL`
3. Enable GitHub Actions.
4. If you use the Mac Studio Codex loop, let `scripts/run_local_dispatch.sh` be the primary sender and Git sync worker.
5. That local run can now push updated `data/state.json`, `data/news.json`, and `data/last_run.json` back to `main`, which keeps the web archive pipeline updating from commits.
6. Manual GitHub fallback runs can temporarily override the per-run range with `min_items_per_run` and `max_items_per_run`.
7. Priority selection uses a shared 4-slot taxonomy across all sources and a GeekNews-specific overlay.
8. To publish the archive site, set GitHub Pages source to `GitHub Actions`.
9. Optional: add repository variable `LAZY_DETAIL_API_URL` after deploying the Vercel lazy-detail API.
10. Do not run the GitHub `news-discord` scheduler and the Mac Studio local dispatch loop at the same time.

## Local Dry Run
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
DRY_RUN=1 python scripts/fetch_and_send.py
```

## Mac Studio Codex Runner
- Repo-local `launchd` setup for scheduled `codex exec` runs lives in [`docs/codex-mac-studio.md`](docs/codex-mac-studio.md).
- Files are under `scripts/run_codex_task.sh`, `ops/codex/`, and `ops/launchd/`.
- The no-OpenAI flow also uses `scripts/process_lazy_detail_queue.mjs` plus `ops/launchd/io.tabber.itnewsletter.lazy-detail-queue-worker.plist`.
- `scripts/run_local_dispatch.sh` is the recommended scheduled dispatcher when you want local Codex title/summary enrichment.
- It can now push only `data/state.json`, `data/news.json`, and `data/last_run.json` back to GitHub automatically after each successful run.
- Do not keep the GitHub `news-discord` scheduler active at the same time as `launchd` local dispatch. They do not share `data/state.json` automatically, so the same items can be sent again later.

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
- `CODEX_SUMMARY_MODEL` (default: empty, use your account default model)
- `CODEX_SUMMARY_TIMEOUT_SEC` (default: `120`)
- `CODEX_SUMMARY_SANDBOX` (default: `read-only`)
- `CODEX_SUMMARY_EXTRA_ARGS` (default: empty)
- `SITE_BASE_URL` (default: `https://itnewsletter.vercel.app`, used for canonical/OG detail-page links)
- `DETAIL_BANNER_AD_SLOT` (default: empty, detail-page banner ad above the briefing section)
- `DETAIL_BANNER_AD_CLIENT` (default: `ca-pub-3668470088067384`)

## Lazy Detail API (legacy English archive items)
- New English items can generate `translated_title`, `short_summary`, and a detail-page `why_it_matters` card during local dispatch through Codex CLI.
- Mac Studio local dispatch can also generate slot-based `topic_digests`, persist them in `data/news.json`, and feed the static `/topics/` pages.
- `detailed_summary` is generated lazily only after the detail page is opened.
- Korean items and GeekNews are excluded from lazy generation.
- Supported legacy sources are controlled by `config/lazy_detail_allowlist.json`.
- HN RSS lazy detail support is limited to curated downstream domains, not the whole HN source.
- The archive detail page never stores or mirrors original article bodies. The API only stores generated `detailed_summary` in Redis.
- The Vercel lazy-detail endpoint now only checks cache and enqueues jobs; your Mac Studio worker generates the briefing and writes it back to Redis.

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
- `UPSTASH_REDIS_REST_URL`
- `UPSTASH_REDIS_REST_TOKEN`
- `SITE_BASE_URL`
  - Example: `https://itnewsletter.vercel.app`
- `DETAIL_BANNER_AD_SLOT`
  - Example: `1234567890`
- `DETAIL_BANNER_AD_CLIENT`
  - Optional override. Default publisher ID is already baked into the build.

Then set GitHub repository variable:
- `LAZY_DETAIL_API_URL`
  - Example: `https://your-project.vercel.app/api/lazy-detail`

And on your Mac Studio, copy and fill:
- `ops/codex/lazy-detail-worker.env.example`

Then run the queue worker locally:

```bash
node scripts/process_lazy_detail_queue.mjs
```

## Notes
- Some newsletters do not expose RSS/Atom feeds directly.
- Add only verified feed URLs to `config/sources.yaml`.
- `source_type: sitemap` + `path_prefix` can be used for sites without RSS (e.g., Anthropic engineering posts).
- New item selection uses a shared 4-slot taxonomy: `practical_tech`, `tools_agents`, `strategy_insight`, `industry_business`.
- GeekNews has source-specific overlay terms and a dynamic cap: up to 2 items in a 5-item batch, up to 3 items in a 6-7 item batch.
- HN now uses the official Hacker News API, keeps a stronger source prior, and enriches stories with HN-native context so technical posts and engineering essays surface more often.
- Product Hunt Feed is currently disabled by default because signal quality was low for the Discord batch.
- GeekNews posts include a short 3-4 line preview from feed summary when AI summary is not used.
- English items can store `translated_title` and `short_summary` at dispatch time through local Codex CLI.
- Korean and GeekNews items do not trigger extra detail-page detail-generation jobs.
- Older allowlisted English articles can request a richer detail briefing on demand through the Vercel API queue.
- Older HN items with a stored HN story id can request richer detail briefings from HN story/comment context without crawling the downstream article body.
- Multiple selected items are grouped into a single Discord push per run (subject to message size limit).
- Batch size is selected automatically within the configured min/max range, shrinking from max to min when the Discord message gets too long.
- Selection logs now include the winning taxonomy slot and matched terms for explainability.
- Items older than 3 days are skipped by default before prioritization.
- The archive site is built from `data/news.json`, enriches older items with taxonomy metadata during the Pages build, and generates static detail pages under `dist/news/<detail-slug>/`.
- HN detail pages now also generate static share-preview PNGs under `dist/og/hn/` and use those images only for `og:image` and `twitter:image`.
- GeekNews and other non-HN detail pages continue to use the shared default icon for social preview metadata.
- The HN OG renderer prefers bundled IBM Plex Sans KR font assets so preview output stays stable across local and Vercel builds.
- Archive detail pages are briefing pages, not mirrored article pages: the site stores metadata, summaries, and original links, but does not mirror full article bodies.
- The list page now highlights the latest sent batch in a dedicated today's curation section.
