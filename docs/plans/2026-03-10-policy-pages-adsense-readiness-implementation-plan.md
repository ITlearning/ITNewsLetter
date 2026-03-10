# Policy Pages For AdSense Readiness Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add policy pages and a shared footer so the archive site reads as a curated briefing product rather than a thin aggregation surface before AdSense integration.

**Architecture:** Create four static policy pages under `site/`, link them from shared footers on the list and detail templates, and lightly adjust list-page copy to clarify the service's briefing/curation role. Rely on the existing site copy step so no extra build pipeline is needed.

**Tech Stack:** Static HTML, vanilla CSS, Python site build tests

---

## File Structure

- Modify: [`site/index.html`](/Users/tabber/ITNewsLetter/site/index.html)
- Modify: [`site/templates/detail.html`](/Users/tabber/ITNewsLetter/site/templates/detail.html)
- Modify: [`site/styles.css`](/Users/tabber/ITNewsLetter/site/styles.css)
- Modify: [`site/detail.css`](/Users/tabber/ITNewsLetter/site/detail.css)
- Create: [`site/about.html`](/Users/tabber/ITNewsLetter/site/about.html)
- Create: [`site/editorial-policy.html`](/Users/tabber/ITNewsLetter/site/editorial-policy.html)
- Create: [`site/privacy.html`](/Users/tabber/ITNewsLetter/site/privacy.html)
- Create: [`site/contact.html`](/Users/tabber/ITNewsLetter/site/contact.html)
- Modify: [`tests/test_build_archive_site.py`](/Users/tabber/ITNewsLetter/tests/test_build_archive_site.py)

## Chunk 1: Static Policy Pages

### Task 1: Add the policy content pages

**Files:**
- Create: [`site/about.html`](/Users/tabber/ITNewsLetter/site/about.html)
- Create: [`site/editorial-policy.html`](/Users/tabber/ITNewsLetter/site/editorial-policy.html)
- Create: [`site/privacy.html`](/Users/tabber/ITNewsLetter/site/privacy.html)
- Create: [`site/contact.html`](/Users/tabber/ITNewsLetter/site/contact.html)

- [ ] Add consistent static pages with concise policy copy.
- [ ] Include links back to the archive and between policy pages.

## Chunk 2: Footer And Copy

### Task 2: Add shared policy navigation

**Files:**
- Modify: [`site/index.html`](/Users/tabber/ITNewsLetter/site/index.html)
- Modify: [`site/templates/detail.html`](/Users/tabber/ITNewsLetter/site/templates/detail.html)
- Modify: [`site/styles.css`](/Users/tabber/ITNewsLetter/site/styles.css)
- Modify: [`site/detail.css`](/Users/tabber/ITNewsLetter/site/detail.css)

- [ ] Add a policy footer to the list page.
- [ ] Add a policy footer to the detail page with nested relative links.
- [ ] Slightly strengthen the list-page intro copy.

## Chunk 3: Verification

### Task 3: Build-output regression coverage

**Files:**
- Modify: [`tests/test_build_archive_site.py`](/Users/tabber/ITNewsLetter/tests/test_build_archive_site.py)

- [ ] Assert policy pages are copied into `dist/`.
- [ ] Assert the detail page footer contains policy links.
- [ ] Run unit tests and lightweight syntax checks.
