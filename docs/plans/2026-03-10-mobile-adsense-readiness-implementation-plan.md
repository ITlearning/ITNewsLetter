# Mobile And AdSense Readiness Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Improve mobile layout quality across the archive site and wire the site for AdSense verification and Auto Ads using the provided publisher ID.

**Architecture:** Add the AdSense script to every static page head and publish an `ads.txt` file at the site root. In parallel, refine the existing responsive CSS so sticky panels, cards, footers, hero blocks, and detail metadata collapse cleanly on narrow screens.

**Tech Stack:** Static HTML, CSS, GitHub Pages, Python build tests

---

## File Structure

- Modify: [`site/index.html`](/Users/tabber/ITNewsLetter/site/index.html)
- Modify: [`site/templates/detail.html`](/Users/tabber/ITNewsLetter/site/templates/detail.html)
- Modify: [`site/about.html`](/Users/tabber/ITNewsLetter/site/about.html)
- Modify: [`site/editorial-policy.html`](/Users/tabber/ITNewsLetter/site/editorial-policy.html)
- Modify: [`site/privacy.html`](/Users/tabber/ITNewsLetter/site/privacy.html)
- Modify: [`site/contact.html`](/Users/tabber/ITNewsLetter/site/contact.html)
- Modify: [`site/styles.css`](/Users/tabber/ITNewsLetter/site/styles.css)
- Modify: [`site/detail.css`](/Users/tabber/ITNewsLetter/site/detail.css)
- Create: [`site/ads.txt`](/Users/tabber/ITNewsLetter/site/ads.txt)
- Modify: [`tests/test_build_archive_site.py`](/Users/tabber/ITNewsLetter/tests/test_build_archive_site.py)

## Chunk 1: AdSense Wiring

### Task 1: Add publisher verification code

**Files:**
- Modify: [`site/index.html`](/Users/tabber/ITNewsLetter/site/index.html)
- Modify: [`site/templates/detail.html`](/Users/tabber/ITNewsLetter/site/templates/detail.html)
- Modify: [`site/about.html`](/Users/tabber/ITNewsLetter/site/about.html)
- Modify: [`site/editorial-policy.html`](/Users/tabber/ITNewsLetter/site/editorial-policy.html)
- Modify: [`site/privacy.html`](/Users/tabber/ITNewsLetter/site/privacy.html)
- Modify: [`site/contact.html`](/Users/tabber/ITNewsLetter/site/contact.html)
- Create: [`site/ads.txt`](/Users/tabber/ITNewsLetter/site/ads.txt)

- [ ] Add the provided AdSense script into each page head.
- [ ] Add the root-level `ads.txt` line for the provided publisher ID.

## Chunk 2: Responsive Layout Polish

### Task 2: Tighten mobile layout behavior

**Files:**
- Modify: [`site/styles.css`](/Users/tabber/ITNewsLetter/site/styles.css)
- Modify: [`site/detail.css`](/Users/tabber/ITNewsLetter/site/detail.css)

- [ ] Relax sticky behavior on small screens.
- [ ] Improve card, hero, footer, button, and metadata wrapping on narrow widths.
- [ ] Make policy pages and detail pages read cleanly on mobile.

## Chunk 3: Verification

### Task 3: Build-output checks

**Files:**
- Modify: [`tests/test_build_archive_site.py`](/Users/tabber/ITNewsLetter/tests/test_build_archive_site.py)

- [ ] Assert the build output includes `ads.txt`.
- [ ] Assert generated pages include the AdSense script.
- [ ] Run the build tests and syntax checks.
