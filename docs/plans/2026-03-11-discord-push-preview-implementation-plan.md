# Discord Push Preview Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a push-friendly top-3 headline preview to the Discord batch message while keeping the existing detailed item blocks below it.

**Architecture:** Extend the Discord batch renderer with a small preview composer that reuses the existing item ordering and title selection rules. Keep message selection behavior unchanged so the existing length-based fallback still evaluates the final rendered content.

**Tech Stack:** Python, unittest

---

## File Structure

- Modify: [`scripts/fetch_and_send.py`](/Users/tabber/ITNewsLetter/scripts/fetch_and_send.py)
- Modify: [`tests/test_fetch_and_send_enrichment.py`](/Users/tabber/ITNewsLetter/tests/test_fetch_and_send_enrichment.py)

## Chunk 1: Preview Rendering

### Task 1: Add the top headline preview section

**Files:**
- Modify: [`scripts/fetch_and_send.py`](/Users/tabber/ITNewsLetter/scripts/fetch_and_send.py)

- [ ] Add a helper that renders up to 3 preview title lines from the selected items.
- [ ] Prefer `translated_title` over the original title and truncate preview titles conservatively.
- [ ] Insert the preview section between the batch header and the existing item blocks.

## Chunk 2: Regression Coverage

### Task 2: Cover the new message shape with tests

**Files:**
- Modify: [`tests/test_fetch_and_send_enrichment.py`](/Users/tabber/ITNewsLetter/tests/test_fetch_and_send_enrichment.py)

- [ ] Add a test that verifies the preview section includes only the first 3 items.
- [ ] Add a test that verifies translated titles are used in the preview.
- [ ] Add a test that verifies the detailed item blocks still remain in the body.

## Chunk 3: Verification

### Task 3: Run targeted tests

**Files:**
- Modify: [`scripts/fetch_and_send.py`](/Users/tabber/ITNewsLetter/scripts/fetch_and_send.py)
- Modify: [`tests/test_fetch_and_send_enrichment.py`](/Users/tabber/ITNewsLetter/tests/test_fetch_and_send_enrichment.py)

- [ ] Run the focused unittest target for `tests/test_fetch_and_send_enrichment.py`.
- [ ] Confirm the new preview section survives the existing content assembly flow without syntax errors.
