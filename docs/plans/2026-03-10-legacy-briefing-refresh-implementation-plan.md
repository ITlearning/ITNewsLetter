# Legacy Briefing Refresh Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Safely refresh legacy plain-text briefings by clearing only lazy-regenerable archive entries and invalidating older lazy-detail Redis cache entries.

**Architecture:** Add a one-off cleanup script that inspects archive items, recognizes already-markdown briefings, and removes only legacy plain-text `detailed_summary` values for items that can be regenerated on demand. In parallel, bump the lazy-detail Redis cache namespace so cached old-format summaries are ignored.

**Tech Stack:** Python 3.9+, vanilla Node.js modules, JSON archive data, Upstash Redis REST API

---

## File Structure

- Modify: [`scripts/fetch_and_send.py`](/Users/tabber/ITNewsLetter/scripts/fetch_and_send.py)
- Create: [`scripts/reset_legacy_briefings.py`](/Users/tabber/ITNewsLetter/scripts/reset_legacy_briefings.py)
- Modify: [`api/_lib/lazy-detail-cache.mjs`](/Users/tabber/ITNewsLetter/api/_lib/lazy-detail-cache.mjs)
- Modify: [`README.md`](/Users/tabber/ITNewsLetter/README.md)
- Modify: [`tests/test_fetch_and_send_enrichment.py`](/Users/tabber/ITNewsLetter/tests/test_fetch_and_send_enrichment.py)
- Create: [`tests/test_reset_legacy_briefings.py`](/Users/tabber/ITNewsLetter/tests/test_reset_legacy_briefings.py)

## Chunk 1: Shared Detection

### Task 1: Detect markdown-shaped briefings

**Files:**
- Modify: [`scripts/fetch_and_send.py`](/Users/tabber/ITNewsLetter/scripts/fetch_and_send.py)
- Modify: [`tests/test_fetch_and_send_enrichment.py`](/Users/tabber/ITNewsLetter/tests/test_fetch_and_send_enrichment.py)

- [ ] Add a reusable helper that distinguishes legacy plain text from the new limited Markdown format.
- [ ] Cover plain text vs paragraph/list/bold cases with unit tests.

## Chunk 2: Cleanup Script And Cache Namespace

### Task 2: Add safe legacy cleanup flow

**Files:**
- Create: [`scripts/reset_legacy_briefings.py`](/Users/tabber/ITNewsLetter/scripts/reset_legacy_briefings.py)
- Modify: [`api/_lib/lazy-detail-cache.mjs`](/Users/tabber/ITNewsLetter/api/_lib/lazy-detail-cache.mjs)
- Create: [`tests/test_reset_legacy_briefings.py`](/Users/tabber/ITNewsLetter/tests/test_reset_legacy_briefings.py)

- [ ] Add a dry-run-first script that reports reset candidates and optionally writes the archive file.
- [ ] Reset only items that remain lazy-regenerable after removing `detailed_summary`.
- [ ] Bump the Redis cache namespace to `v2`.

## Chunk 3: Docs And Execution

### Task 3: Document and run the refresh path

**Files:**
- Modify: [`README.md`](/Users/tabber/ITNewsLetter/README.md)

- [ ] Document dry-run and apply commands for archive cleanup.
- [ ] Document that `v2` cache keys invalidate previously generated lazy-detail summaries.
