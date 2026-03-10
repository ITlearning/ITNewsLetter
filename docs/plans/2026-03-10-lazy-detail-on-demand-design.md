# Lazy Detail On-Demand Design

## Goal

Keep the static archive on GitHub Pages, but make older English archive items capable of showing a richer detail briefing on demand.

## Product Decision

- New English items continue to store `translated_title`, `short_summary`, and `detailed_summary` at dispatch time.
- Legacy archive items do not get a full backfill job.
- Instead, the detail page tries a one-time on-demand summary generation only when the user opens the page.

## Architecture

- `GitHub Pages` serves static archive pages and static detail pages.
- `Vercel Function` handles on-demand detail generation.
- `Redis on Vercel` stores generated `detailed_summary` results by article id.

## Safety Rules

- Only English source articles are eligible.
- GeekNews and Korean news sources are excluded.
- Eligibility is gated by an allowlist of source domains.
- Original article body text is fetched temporarily but never stored.
- Only generated `detailed_summary` is cached.

## Detail Page Flow

1. Static detail page loads.
2. If `detailed_summary` already exists, render it immediately.
3. If it is missing and the item is `lazy_detail_supported`, client calls the Vercel API.
4. API checks Redis cache by article id.
5. If cache miss, API fetches the original page, extracts text, asks OpenAI for a Korean detail summary, stores the result in Redis, and returns it.
6. If unsupported or failed, the page keeps the existing `short_summary` fallback and shows a short status message.

## API Response

```json
{
  "status": "cached | generated | unsupported | failed",
  "detailed_summary": "...",
  "message": "...",
  "cached": true
}
```

## Required Runtime Config

- GitHub Pages build env:
  - `LAZY_DETAIL_API_URL`
- Vercel env:
  - `OPENAI_API_KEY`
  - `OPENAI_MODEL`
  - `UPSTASH_REDIS_REST_URL`
  - `UPSTASH_REDIS_REST_TOKEN`

## Non-Goals

- No full body mirroring
- No lazy generation for GeekNews
- No lazy generation for Korean sources
- No bulk backfill job
