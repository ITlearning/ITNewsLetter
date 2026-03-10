# Curation Detail Phase 1 Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add curation-oriented detail pages, related articles, and a today's curation section to the sent-news archive without mirroring original article bodies.

**Architecture:** Extend dispatch-time enrichment to persist detail-safe summary fields for English items, then expand the static archive builder to generate both an archive index payload and per-item detail pages. Keep the site fully static by deriving related items and the latest dispatch batch at build time, and reuse existing archive metadata for Korean and GeekNews items without adding new scraping behavior.

**Tech Stack:** Python 3.9+, stdlib `unittest`, existing `scripts/fetch_and_send.py`, existing `scripts/build_archive_site.py`, static HTML/CSS/vanilla JS in `site/`, GitHub Pages deployment, `@brainstorming`, `@ui-ux-pro-max`

---

## File Structure

- Modify: [`scripts/fetch_and_send.py`](/Users/tabber/ITNewsLetter/scripts/fetch_and_send.py)
  - Persist `detail_slug`, `is_english_source`, and `detailed_summary` for sent items.
  - Split OpenAI enrichment into list-summary and detail-summary aware output.
- Modify: [`scripts/build_archive_site.py`](/Users/tabber/ITNewsLetter/scripts/build_archive_site.py)
  - Build index payload additions, derive related items, derive today's curation, and emit detail pages.
- Modify: [`site/index.html`](/Users/tabber/ITNewsLetter/site/index.html)
  - Add today's curation block and list-to-detail navigation hooks.
- Modify: [`site/app.js`](/Users/tabber/ITNewsLetter/site/app.js)
  - Render today's curation and route cards/links to detail pages.
- Modify: [`site/styles.css`](/Users/tabber/ITNewsLetter/site/styles.css)
  - Style today's curation strip and detail-entry affordances.
- Create: [`site/detail.css`](/Users/tabber/ITNewsLetter/site/detail.css)
  - Dedicated styles for the briefing detail page.
- Create: [`site/detail.js`](/Users/tabber/ITNewsLetter/site/detail.js)
  - Minimal progressive enhancement for detail navigation if needed.
- Create: [`site/templates/detail.html`](/Users/tabber/ITNewsLetter/site/templates/detail.html)
  - Static HTML template copied and filled by the build script.
- Create: [`tests/test_build_archive_site.py`](/Users/tabber/ITNewsLetter/tests/test_build_archive_site.py)
  - Verify payload derivation, detail page generation, related items, and today's curation behavior.
- Create: [`tests/test_fetch_and_send_enrichment.py`](/Users/tabber/ITNewsLetter/tests/test_fetch_and_send_enrichment.py)
  - Verify English-only detail summary generation and Korean fallback behavior.
- Modify: [`README.md`](/Users/tabber/ITNewsLetter/README.md)
  - Document detail pages, today's curation, and the English-summary policy.

## Spec References

- Design spec: [`docs/plans/2026-03-10-curation-detail-phase1-design.md`](/Users/tabber/ITNewsLetter/docs/plans/2026-03-10-curation-detail-phase1-design.md)
- Prior archive design: [`docs/plans/2026-03-10-web-archive-design.md`](/Users/tabber/ITNewsLetter/docs/plans/2026-03-10-web-archive-design.md)
- Archive layout follow-up: [`docs/plans/2026-03-10-web-archive-list-layout-design.md`](/Users/tabber/ITNewsLetter/docs/plans/2026-03-10-web-archive-list-layout-design.md)

## Chunk 1: Dispatch-Time Data Model

### Task 1: Add Detail-Safe Fields To Sent Items

**Files:**
- Modify: [`scripts/fetch_and_send.py`](/Users/tabber/ITNewsLetter/scripts/fetch_and_send.py)
- Test: [`tests/test_fetch_and_send_enrichment.py`](/Users/tabber/ITNewsLetter/tests/test_fetch_and_send_enrichment.py)

- [ ] **Step 1: Write failing unit tests for English enrichment output**

```python
import unittest
from scripts.fetch_and_send import enrich_item_with_openai


class EnrichmentTests(unittest.TestCase):
    def test_english_item_can_store_detailed_summary(self):
        item = {"title": "OpenAI ships new coding workflow", "summary": "..." }
        # mock OpenAI response parsing helper
        self.assertIn("detailed_summary", enriched)
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `python3 -m unittest tests.test_fetch_and_send_enrichment -v`  
Expected: FAIL because `detailed_summary` and related helpers do not exist yet.

- [ ] **Step 3: Add helper functions for detail-safe metadata**

Implement in [`scripts/fetch_and_send.py`](/Users/tabber/ITNewsLetter/scripts/fetch_and_send.py):

```python
def slugify_archive_item(item: dict[str, Any]) -> str: ...
def is_english_item(item: dict[str, Any]) -> bool: ...
```

Rules:
- `detail_slug` must be deterministic and stable across rebuilds.
- Prefer `id` if present, otherwise derive from title/date.
- `is_english_source` must be `True` only when the item should go through OpenAI enrichment.

- [ ] **Step 4: Extend the OpenAI JSON schema**

Update the prompt and parse path in [`scripts/fetch_and_send.py`](/Users/tabber/ITNewsLetter/scripts/fetch_and_send.py) to request:

```json
{
  "translated_title": "",
  "short_summary": "",
  "detailed_summary": ""
}
```

Constraints:
- `short_summary`: 1-2 sentences, list page safe
- `detailed_summary`: 4-7 sentences, detail page safe
- Never request or store full article body reconstruction

- [ ] **Step 5: Apply Korean/GeekNews fallback behavior**

Implementation rules in [`scripts/fetch_and_send.py`](/Users/tabber/ITNewsLetter/scripts/fetch_and_send.py):
- Korean-dominant items: skip new GPT call
- GeekNews items: skip new GPT call for detail pages
- If `detailed_summary` is absent, keep item valid with existing `short_summary`

- [ ] **Step 6: Persist new fields into `data/news.json` merge output**

Ensure sent items written by `merge_news()` retain:
- `detail_slug`
- `is_english_source`
- `detailed_summary`

- [ ] **Step 7: Run tests again**

Run: `python3 -m unittest tests.test_fetch_and_send_enrichment -v`  
Expected: PASS

- [ ] **Step 8: Run syntax validation**

Run: `env PYTHONPYCACHEPREFIX=.pycache python3 -m py_compile scripts/fetch_and_send.py`  
Expected: no output

- [ ] **Step 9: Commit**

```bash
git add scripts/fetch_and_send.py tests/test_fetch_and_send_enrichment.py
git commit -m "feat: persist archive detail summary fields"
```

## Chunk 2: Static Detail Page Generation

### Task 2: Expand Build Script To Emit Detail Pages

**Files:**
- Modify: [`scripts/build_archive_site.py`](/Users/tabber/ITNewsLetter/scripts/build_archive_site.py)
- Create: [`site/templates/detail.html`](/Users/tabber/ITNewsLetter/site/templates/detail.html)
- Create: [`site/detail.css`](/Users/tabber/ITNewsLetter/site/detail.css)
- Create: [`site/detail.js`](/Users/tabber/ITNewsLetter/site/detail.js)
- Test: [`tests/test_build_archive_site.py`](/Users/tabber/ITNewsLetter/tests/test_build_archive_site.py)

- [ ] **Step 1: Write failing tests for detail page generation**

Test cases in [`tests/test_build_archive_site.py`](/Users/tabber/ITNewsLetter/tests/test_build_archive_site.py):
- build writes `dist/news/<slug>/index.html`
- detail page falls back to `short_summary` when `detailed_summary` is missing
- detail page excludes mirrored source body text

- [ ] **Step 2: Run tests to verify they fail**

Run: `python3 -m unittest tests.test_build_archive_site -v`  
Expected: FAIL because detail build output does not exist yet.

- [ ] **Step 3: Normalize archive build data**

Refactor [`scripts/build_archive_site.py`](/Users/tabber/ITNewsLetter/scripts/build_archive_site.py) into smaller build helpers:

```python
def build_archive_items(...): ...
def derive_today_picks(...): ...
def derive_related_items(...): ...
def render_detail_page(...): ...
def write_detail_pages(...): ...
```

Rules:
- Keep build-time derivation pure and deterministic.
- Do not mutate original `raw_items` in place.

- [ ] **Step 4: Add detail page rendering template**

Create [`site/templates/detail.html`](/Users/tabber/ITNewsLetter/site/templates/detail.html) with placeholders for:
- translated title
- original title
- metadata row
- `detailed_summary`
- matched terms
- original source CTA
- previous/next links
- related items

- [ ] **Step 5: Add detail-specific styles and minimal JS**

Create:
- [`site/detail.css`](/Users/tabber/ITNewsLetter/site/detail.css)
- [`site/detail.js`](/Users/tabber/ITNewsLetter/site/detail.js)

Requirements:
- narrow reading column
- paper/editorial visual direction
- obvious primary CTA to source
- no heavy motion

- [ ] **Step 6: Emit build-time detail metadata into index payload**

Ensure archive items in `dist/data/news-archive.json` include:
- `detail_slug`
- `detail_url`
- `has_detailed_summary`

- [ ] **Step 7: Generate previous/next navigation in detail pages**

Rules:
- use archive chronological order
- skip broken items without `detail_slug`
- do not generate self-links

- [ ] **Step 8: Run tests again**

Run: `python3 -m unittest tests.test_build_archive_site -v`  
Expected: PASS for detail page generation and fallback cases

- [ ] **Step 9: Run build verification**

Run: `python3 scripts/build_archive_site.py`  
Expected:
- `dist/index.html`
- `dist/data/news-archive.json`
- `dist/news/<slug>/index.html`

- [ ] **Step 10: Commit**

```bash
git add scripts/build_archive_site.py site/templates/detail.html site/detail.css site/detail.js tests/test_build_archive_site.py
git commit -m "feat: generate static archive detail pages"
```

## Chunk 3: Related Articles And Today's Curation

### Task 3: Add Related Item Derivation

**Files:**
- Modify: [`scripts/build_archive_site.py`](/Users/tabber/ITNewsLetter/scripts/build_archive_site.py)
- Test: [`tests/test_build_archive_site.py`](/Users/tabber/ITNewsLetter/tests/test_build_archive_site.py)

- [ ] **Step 1: Write failing tests for related item ranking**

Cover:
- same slot beats same source
- overlapping matched terms raises rank
- current item is excluded
- maximum of 3 related items

- [ ] **Step 2: Run targeted test**

Run: `python3 -m unittest tests.test_build_archive_site.RelatedItemsTests -v`  
Expected: FAIL because related ranking helper does not exist yet.

- [ ] **Step 3: Implement a small related ranking helper**

Add to [`scripts/build_archive_site.py`](/Users/tabber/ITNewsLetter/scripts/build_archive_site.py):

```python
def score_related_item(base_item: dict[str, Any], candidate: dict[str, Any]) -> int: ...
```

Recommended scoring:
- same `primary_slot`: `+6`
- each shared `matched_term`: `+2`
- same `source`: `+1`
- chronological closeness tie-breaker

- [ ] **Step 4: Attach related items to generated detail context**

Store only safe fields for rendering:
- title
- translated title
- detail URL
- slot label
- source
- sent date

- [ ] **Step 5: Re-run related tests**

Run: `python3 -m unittest tests.test_build_archive_site.RelatedItemsTests -v`  
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add scripts/build_archive_site.py tests/test_build_archive_site.py
git commit -m "feat: add related archive recommendations"
```

### Task 4: Add Today's Curation To The Index Experience

**Files:**
- Modify: [`scripts/build_archive_site.py`](/Users/tabber/ITNewsLetter/scripts/build_archive_site.py)
- Modify: [`site/index.html`](/Users/tabber/ITNewsLetter/site/index.html)
- Modify: [`site/app.js`](/Users/tabber/ITNewsLetter/site/app.js)
- Modify: [`site/styles.css`](/Users/tabber/ITNewsLetter/site/styles.css)
- Test: [`tests/test_build_archive_site.py`](/Users/tabber/ITNewsLetter/tests/test_build_archive_site.py)

- [ ] **Step 1: Write failing tests for today's curation payload**

Cover:
- latest dispatch window is identified from `sent_at`
- only latest batch items are marked as today picks
- missing dispatch info degrades gracefully

- [ ] **Step 2: Run targeted test**

Run: `python3 -m unittest tests.test_build_archive_site.TodayCurationTests -v`  
Expected: FAIL because today-pick derivation is missing.

- [ ] **Step 3: Implement latest batch derivation**

Add helper in [`scripts/build_archive_site.py`](/Users/tabber/ITNewsLetter/scripts/build_archive_site.py):

```python
def derive_today_picks(items: list[dict[str, Any]]) -> list[dict[str, Any]]: ...
```

Rules:
- prefer exact latest `sent_at` batch
- fallback to most recent few items when dispatch timestamps are sparse
- cap UI payload to the latest 5-7 items already sent

- [ ] **Step 4: Add today's curation markup**

Update [`site/index.html`](/Users/tabber/ITNewsLetter/site/index.html) to include:
- section heading
- compact curated list container
- empty-state-safe rendering hook

- [ ] **Step 5: Render today's curation in client JS**

Update [`site/app.js`](/Users/tabber/ITNewsLetter/site/app.js):
- populate today picks before the full archive list
- use same title/summary fallbacks as list cards
- link entries to detail pages instead of only raw source URLs

- [ ] **Step 6: Style the curation block**

Update [`site/styles.css`](/Users/tabber/ITNewsLetter/site/styles.css):
- compact editorial band
- stronger hierarchy than ordinary list rows
- mobile-safe stacking

- [ ] **Step 7: Re-run targeted tests**

Run: `python3 -m unittest tests.test_build_archive_site.TodayCurationTests -v`  
Expected: PASS

- [ ] **Step 8: Run client/build verification**

Run:

```bash
node --check site/app.js
python3 scripts/build_archive_site.py
```

Expected: no syntax errors, today's curation rendered into built JSON/index

- [ ] **Step 9: Commit**

```bash
git add scripts/build_archive_site.py site/index.html site/app.js site/styles.css tests/test_build_archive_site.py
git commit -m "feat: highlight today's curation on archive"
```

## Chunk 4: Finish, Docs, And Manual Verification

### Task 5: Final Documentation And Smoke Test

**Files:**
- Modify: [`README.md`](/Users/tabber/ITNewsLetter/README.md)
- Modify: [`docs/plans/2026-03-10-curation-detail-phase1-design.md`](/Users/tabber/ITNewsLetter/docs/plans/2026-03-10-curation-detail-phase1-design.md) if implementation constraints changed

- [ ] **Step 1: Document new archive behavior**

Update [`README.md`](/Users/tabber/ITNewsLetter/README.md) with:
- detail page generation
- English-only `detailed_summary`
- no body mirroring policy
- related articles and today's curation behavior

- [ ] **Step 2: Run full validation set**

Run:

```bash
python3 -m unittest tests.test_fetch_and_send_enrichment tests.test_build_archive_site -v
env PYTHONPYCACHEPREFIX=.pycache python3 -m py_compile scripts/fetch_and_send.py scripts/build_archive_site.py
node --check site/app.js
python3 scripts/build_archive_site.py
```

Expected:
- all tests pass
- no Python syntax errors
- no JS syntax errors
- `dist/news/` pages generated

- [ ] **Step 3: Manual file checks**

Verify:
- [ ] `dist/data/news-archive.json` includes `today_picks`
- [ ] a sample `dist/news/<slug>/index.html` renders `detailed_summary`
- [ ] Korean sample page falls back to `short_summary`
- [ ] related items block is absent or clean when no matches exist

- [ ] **Step 4: Commit**

```bash
git add README.md docs/plans/2026-03-10-curation-detail-phase1-design.md
git commit -m "docs: describe curation detail archive experience"
```

- [ ] **Step 5: Push**

```bash
git push origin main
```

## Notes For Execution

- Keep commits scoped to each chunk. Do not batch the whole feature into one commit.
- Prefer stdlib `unittest` over adding `pytest` just for this feature.
- Do not add any crawling of article bodies.
- Do not add detail-page-only GPT calls for Korean or GeekNews items.
- Reuse existing archive fields whenever possible; derive presentation fields at build time.

Plan complete and saved to `docs/plans/2026-03-10-curation-detail-phase1-implementation-plan.md`. Ready to execute?
