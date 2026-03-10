# Lazy Detail On-Demand Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add on-demand detailed briefing generation for legacy English archive detail pages without mirroring source article bodies.

**Architecture:** Keep archive HTML fully static, mark eligible detail pages during the existing Pages build, and let the detail page call a small Vercel function when `detailed_summary` is missing. The function uses an allowlisted source policy, OpenAI for summary generation, and Redis for result caching keyed by article id.

**Tech Stack:** Python 3.9+, vanilla JS, GitHub Pages, Vercel Functions (Node.js runtime), Redis REST API, OpenAI Chat Completions API

---

## File Structure

- Modify: [`scripts/build_archive_site.py`](/Users/tabber/ITNewsLetter/scripts/build_archive_site.py)
- Modify: [`site/templates/detail.html`](/Users/tabber/ITNewsLetter/site/templates/detail.html)
- Modify: [`site/detail.js`](/Users/tabber/ITNewsLetter/site/detail.js)
- Modify: [`.github/workflows/news-archive-pages.yml`](/Users/tabber/ITNewsLetter/.github/workflows/news-archive-pages.yml)
- Modify: [`README.md`](/Users/tabber/ITNewsLetter/README.md)
- Create: [`config/lazy_detail_allowlist.json`](/Users/tabber/ITNewsLetter/config/lazy_detail_allowlist.json)
- Create: [`api/lazy-detail.js`](/Users/tabber/ITNewsLetter/api/lazy-detail.js)
- Create: [`api/_lib/lazy-detail-config.js`](/Users/tabber/ITNewsLetter/api/_lib/lazy-detail-config.js)
- Create: [`api/_lib/lazy-detail-cache.js`](/Users/tabber/ITNewsLetter/api/_lib/lazy-detail-cache.js)
- Create: [`api/_lib/lazy-detail-extract.js`](/Users/tabber/ITNewsLetter/api/_lib/lazy-detail-extract.js)
- Create: [`api/_lib/lazy-detail-openai.js`](/Users/tabber/ITNewsLetter/api/_lib/lazy-detail-openai.js)
- Modify: [`tests/test_build_archive_site.py`](/Users/tabber/ITNewsLetter/tests/test_build_archive_site.py)

## Chunk 1: Eligibility And Build-Time Marking

### Task 1: Mark Eligible Detail Pages

**Files:**
- Modify: [`scripts/build_archive_site.py`](/Users/tabber/ITNewsLetter/scripts/build_archive_site.py)
- Create: [`config/lazy_detail_allowlist.json`](/Users/tabber/ITNewsLetter/config/lazy_detail_allowlist.json)
- Modify: [`tests/test_build_archive_site.py`](/Users/tabber/ITNewsLetter/tests/test_build_archive_site.py)

- [ ] Add a JSON allowlist for domains and excluded sources.
- [ ] Load the allowlist in the build script.
- [ ] Mark archive items with:
  - `lazy_detail_supported`
  - `lazy_detail_reason`
  - `lazy_detail_api_url`
- [ ] Extend detail page build context with those fields.
- [ ] Add tests for allowlist acceptance/rejection.

## Chunk 2: Static Detail Page Client Hook

### Task 2: Add Lazy Detail Client Flow

**Files:**
- Modify: [`site/templates/detail.html`](/Users/tabber/ITNewsLetter/site/templates/detail.html)
- Modify: [`site/detail.js`](/Users/tabber/ITNewsLetter/site/detail.js)

- [ ] Embed serialized detail metadata into the page.
- [ ] Add a status block below the summary area.
- [ ] If `detailed_summary` is missing and lazy detail is supported, call the API automatically.
- [ ] Update the summary and status text based on API response.

## Chunk 3: Vercel API

### Task 3: Implement `api/lazy-detail.js`

**Files:**
- Create: [`api/lazy-detail.js`](/Users/tabber/ITNewsLetter/api/lazy-detail.js)
- Create: [`api/_lib/lazy-detail-config.js`](/Users/tabber/ITNewsLetter/api/_lib/lazy-detail-config.js)
- Create: [`api/_lib/lazy-detail-cache.js`](/Users/tabber/ITNewsLetter/api/_lib/lazy-detail-cache.js)
- Create: [`api/_lib/lazy-detail-extract.js`](/Users/tabber/ITNewsLetter/api/_lib/lazy-detail-extract.js)
- Create: [`api/_lib/lazy-detail-openai.js`](/Users/tabber/ITNewsLetter/api/_lib/lazy-detail-openai.js)

- [ ] Validate request payload and CORS.
- [ ] Re-check eligibility against the allowlist.
- [ ] Read/write cached summaries via Redis REST API.
- [ ] Fetch the original article HTML without persisting it.
- [ ] Extract a bounded plain-text snippet.
- [ ] Generate `detailed_summary` via OpenAI.
- [ ] Return `cached/generated/unsupported/failed` response shape.

## Chunk 4: Ops And Docs

### Task 4: Wire Build Config And Docs

**Files:**
- Modify: [`.github/workflows/news-archive-pages.yml`](/Users/tabber/ITNewsLetter/.github/workflows/news-archive-pages.yml)
- Modify: [`README.md`](/Users/tabber/ITNewsLetter/README.md)

- [ ] Pass `LAZY_DETAIL_API_URL` into the Pages build.
- [ ] Document required GitHub Pages env and Vercel env settings.
- [ ] Document that Redis on Vercel replaces the older Vercel KV product.
