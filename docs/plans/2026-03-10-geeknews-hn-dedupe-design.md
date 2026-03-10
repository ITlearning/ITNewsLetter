# GeekNews Direct Link And HN-Preferred Dedupe Design

## Goal
- Open GeekNews items directly on the GeekNews topic page instead of the local detail page.
- Prefer Hacker News over GeekNews when both sources surface the same story.

## Decisions
- Treat all GeekNews archive cards and related links as direct source links.
- Keep generating GeekNews detail pages for compatibility, but stop routing normal navigation to them.
- Detect HN/GeekNews duplicates with lightweight title similarity:
  - Compare GeekNews Korean title against HN translated title when available.
  - Fall back to normalized titles and token overlap.
- Apply the same dedupe rule in three places:
  - selected batch items
  - merged archive history
  - archive site build

## Non-Goals
- No GeekNews topic-page crawling for original source extraction.
- No cross-source global dedupe beyond the HN-vs-GeekNews case.

## Files
- `scripts/fetch_and_send.py`
- `scripts/build_archive_site.py`
- `site/app.js`
- `tests/test_fetch_and_send_enrichment.py`
- `tests/test_build_archive_site.py`
