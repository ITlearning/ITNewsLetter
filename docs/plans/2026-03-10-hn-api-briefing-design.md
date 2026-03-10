# Hacker News API Briefing Design

## Goal
- Replace HN RSS ingestion with the official Hacker News API.
- Improve HN batch translation quality by using HN story metadata, text, and comment context.
- Allow HN archive detail briefings without depending on downstream article-domain allowlists.

## Decisions
- Keep the public source label as `Hacker News Frontpage (HN RSS)` for archive continuity, but switch the fetch path to the official HN API.
- Add a new `hn_api` source type and fetch top stories from the official Firebase API.
- For HN items, collect story metadata plus a short preview of top-level HN comments.
- Use that HN context both for dispatch-time OpenAI enrichment and for archive lazy detail generation.
- Treat HN items with a valid `hn_story_id` as lazy-detail supported even when the outbound article domain is not allowlisted.

## Data Flow
- Source fetch:
  - Read `topstories.json`
  - Fetch item JSON for the configured story count
  - Fetch a small number of readable top-level comments per story
- Dispatch enrichment:
  - Build a richer prompt for HN items using title, text, score, comment count, and comment preview
- Archive build:
  - Persist `hn_story_id`, `hn_story_type`, `hn_points`, `hn_comments_count`
- Lazy detail API:
  - If the item is HN and has `hn_story_id`, fetch HN item/comment context directly from the official API
  - Generate `detailed_summary` from HN-native context instead of crawling the outbound article

## Safety Rules
- HN-native briefing uses HN API metadata and comments, not the linked article body.
- Downstream article crawling rules remain unchanged for non-HN sources.
- Product Hunt remains disabled, not removed.

## Files
- `config/sources.yaml`
- `scripts/fetch_and_send.py`
- `scripts/build_archive_site.py`
- `api/_lib/lazy-detail-config.mjs`
- `api/_lib/lazy-detail-hn.mjs`
- `api/lazy-detail.mjs`
- `tests/test_fetch_and_send_enrichment.py`
- `tests/test_build_archive_site.py`
