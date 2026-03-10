# Humanized Briefing Markdown Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Keep `detailed_summary` length generous while storing a limited Markdown string and rendering it safely in static and lazy-loaded detail views.

**Architecture:** Reuse one constrained Markdown shape across the Python enrichment pipeline, static site build, and lazy detail API. Normalize the stored string once, render only paragraphs, bullet lists, and bold, and keep client-side reveal behavior compatible with the richer markup.

**Tech Stack:** Python 3.9+, vanilla JS, static HTML/CSS, OpenAI Chat Completions API

---

## File Structure

- Modify: [`scripts/fetch_and_send.py`](/Users/tabber/ITNewsLetter/scripts/fetch_and_send.py)
- Modify: [`scripts/build_archive_site.py`](/Users/tabber/ITNewsLetter/scripts/build_archive_site.py)
- Modify: [`site/templates/detail.html`](/Users/tabber/ITNewsLetter/site/templates/detail.html)
- Modify: [`site/detail.js`](/Users/tabber/ITNewsLetter/site/detail.js)
- Modify: [`site/detail.css`](/Users/tabber/ITNewsLetter/site/detail.css)
- Modify: [`api/_lib/lazy-detail-openai.mjs`](/Users/tabber/ITNewsLetter/api/_lib/lazy-detail-openai.mjs)
- Modify: [`tests/test_fetch_and_send_enrichment.py`](/Users/tabber/ITNewsLetter/tests/test_fetch_and_send_enrichment.py)

## Chunk 1: Shared Briefing Format

### Task 1: Lock the stored Markdown contract

**Files:**
- Modify: [`scripts/fetch_and_send.py`](/Users/tabber/ITNewsLetter/scripts/fetch_and_send.py)
- Modify: [`api/_lib/lazy-detail-openai.mjs`](/Users/tabber/ITNewsLetter/api/_lib/lazy-detail-openai.mjs)

- [ ] Align OpenAI prompt instructions on the same limited Markdown structure.
- [ ] Normalize returned `detailed_summary` strings before storing or returning them.

## Chunk 2: Static And Lazy Detail Rendering

### Task 2: Render limited Markdown safely

**Files:**
- Modify: [`scripts/build_archive_site.py`](/Users/tabber/ITNewsLetter/scripts/build_archive_site.py)
- Modify: [`site/templates/detail.html`](/Users/tabber/ITNewsLetter/site/templates/detail.html)
- Modify: [`site/detail.js`](/Users/tabber/ITNewsLetter/site/detail.js)
- Modify: [`site/detail.css`](/Users/tabber/ITNewsLetter/site/detail.css)

- [ ] Pass the normalized Markdown string into the detail page.
- [ ] Render paragraphs, bullet lists, and bold safely on first load and lazy updates.
- [ ] Preserve reveal animation without flattening lists or inline emphasis.

## Chunk 3: Regression Coverage

### Task 3: Add tests and verification

**Files:**
- Modify: [`tests/test_fetch_and_send_enrichment.py`](/Users/tabber/ITNewsLetter/tests/test_fetch_and_send_enrichment.py)

- [ ] Add normalization coverage for bullet conversion and blank-line cleanup.
- [ ] Add HTML rendering coverage for safe bold/list output and escaping.
- [ ] Run targeted tests plus lightweight syntax verification for touched JS.
