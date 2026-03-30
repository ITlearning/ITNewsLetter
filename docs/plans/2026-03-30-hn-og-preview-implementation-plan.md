# Hacker News OG Preview Image Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Generate HN-only static PNG OG preview images at build time and wire them into detail-page metadata without changing visible detail-page content.

**Architecture:** Keep all logic inside the existing Python archive builder. `scripts/build_archive_site.py` should render one `1200x630` PNG per qualifying Hacker News detail item, write it to `dist/og/hn/`, and pass per-item OG metadata into the existing detail template. Non-HN pages should keep the current shared icon path, and HN image-generation failures should fall back to that default metadata instead of breaking the build.

**Tech Stack:** Python 3.9+, Pillow, unittest, static HTML templates

---

## File Structure

- Modify: [`scripts/build_archive_site.py`](/tmp/itnewsletter-hn-og-image/scripts/build_archive_site.py)
- Modify: [`site/templates/detail.html`](/tmp/itnewsletter-hn-og-image/site/templates/detail.html)
- Modify: [`tests/test_build_archive_site.py`](/tmp/itnewsletter-hn-og-image/tests/test_build_archive_site.py)
- Modify: [`requirements.txt`](/tmp/itnewsletter-hn-og-image/requirements.txt)
- Modify: [`README.md`](/tmp/itnewsletter-hn-og-image/README.md)
- Create: [`scripts/assets/fonts/IBMPlexSansKR-Regular.ttf`](/tmp/itnewsletter-hn-og-image/scripts/assets/fonts/IBMPlexSansKR-Regular.ttf)
- Create: [`scripts/assets/fonts/IBMPlexSansKR-Bold.ttf`](/tmp/itnewsletter-hn-og-image/scripts/assets/fonts/IBMPlexSansKR-Bold.ttf)

## Chunk 1: Lock HN OG Metadata Expectations First

### Task 1: Extend the build regression test before implementing rendering

**Files:**
- Modify: [`tests/test_build_archive_site.py`](/tmp/itnewsletter-hn-og-image/tests/test_build_archive_site.py)

- [ ] Extend `BuildSiteTests.test_build_site_generates_detail_pages_and_safe_fallback` so the HN detail case asserts a generated preview file exists at `dist/og/hn/hn-safe.png`.
- [ ] Add assertions that the HN detail HTML uses `https://itnewsletter.vercel.app/og/hn/hn-safe.png` for both `og:image` and `twitter:image`.
- [ ] Add assertions that the HN detail HTML switches `twitter:card` to `summary_large_image`.
- [ ] Add assertions that the HN detail HTML switches `og:image:width` and `og:image:height` to `1200` and `630`.
- [ ] Keep explicit assertions that the non-HN English detail page still uses `https://itnewsletter.vercel.app/img.icons8.png`.
- [ ] Keep explicit assertions that the non-HN English detail page still uses `twitter:card` `summary`.
- [ ] Add one assertion that the HN detail body still does not gain any new OG preview `<img>` markup in the visible article content.
- [ ] Run `python3 -m unittest tests.test_build_archive_site.BuildSiteTests.test_build_site_generates_detail_pages_and_safe_fallback -v`.
- [ ] Confirm the run fails on the new HN preview assertions before touching implementation.
- [ ] Commit only the failing-test change.

## Chunk 2: Render Static HN Preview PNG Assets

### Task 2: Add the build-time OG image renderer and asset writer

**Files:**
- Modify: [`scripts/build_archive_site.py`](/tmp/itnewsletter-hn-og-image/scripts/build_archive_site.py)
- Create: [`scripts/assets/fonts/IBMPlexSansKR-Regular.ttf`](/tmp/itnewsletter-hn-og-image/scripts/assets/fonts/IBMPlexSansKR-Regular.ttf)
- Create: [`scripts/assets/fonts/IBMPlexSansKR-Bold.ttf`](/tmp/itnewsletter-hn-og-image/scripts/assets/fonts/IBMPlexSansKR-Bold.ttf)

- [ ] Add constants for the HN OG output directory, image size (`1200x630`), and bundled font paths near the existing build constants.
- [ ] Add a narrow helper that identifies HN items eligible for OG generation using `source`, `detail_slug`, and title availability.
- [ ] Add a helper that derives the primary card title from `translated_title` first, then falls back to `title`.
- [ ] Add a helper that derives the secondary line from `title` only when it differs from the primary line.
- [ ] Add a helper that wraps and truncates title text predictably for a fixed-size image instead of letting the renderer overflow.
- [ ] Add a helper that loads the bundled fonts with a readable fallback if the font asset is unavailable.
- [ ] Add a Pillow-based renderer that draws the approved brand-style card: bright layered background, `IT Dispatch Archive` brand lockup, small `Hacker News` chip, dominant translated title, and secondary original title.
- [ ] Reuse existing brand cues already present in the site styles rather than inventing a new palette or layout language.
- [ ] Add a helper that writes the PNG to `dist/og/hn/<detail-slug>.png` and returns the corresponding absolute asset URL.
- [ ] Log per-item rendering failures with the item id or detail slug plus the failure reason, then return default metadata instead of raising for that item.
- [ ] Run the same focused unittest target again.
- [ ] Expect the test to still fail until the detail template is wired to consume the new metadata.
- [ ] Commit the renderer helpers and font assets.

## Chunk 3: Wire Per-Item Metadata Into Detail Pages

### Task 3: Replace the one-size-fits-all OG metadata path with item-specific values

**Files:**
- Modify: [`scripts/build_archive_site.py`](/tmp/itnewsletter-hn-og-image/scripts/build_archive_site.py)
- Modify: [`site/templates/detail.html`](/tmp/itnewsletter-hn-og-image/site/templates/detail.html)

- [ ] Update the detail template placeholders so `og:image:width`, `og:image:height`, and `twitter:card` are parameterized instead of hard-coded.
- [ ] Add a small metadata builder in `render_detail_page` or an adjacent helper that returns the default icon metadata for non-HN pages.
- [ ] Call the HN renderer helper only for qualifying HN items and inject the generated URL plus `1200x630` metadata into the template substitution.
- [ ] Keep the current shared icon metadata path for non-HN pages without changing their visible layout.
- [ ] Keep the visible detail-page body unchanged: no OG preview image element, no new section, no hero image.
- [ ] Make sure a failed HN render falls back cleanly to the same default icon metadata the non-HN path uses.
- [ ] Run `python3 -m unittest tests.test_build_archive_site.BuildSiteTests.test_build_site_generates_detail_pages_and_safe_fallback -v`.
- [ ] Confirm the focused test now passes.
- [ ] Commit the metadata/template wiring.

## Chunk 4: Dependency, Documentation, And Regression Coverage

### Task 4: Update the build environment and explain the new HN-only behavior

**Files:**
- Modify: [`requirements.txt`](/tmp/itnewsletter-hn-og-image/requirements.txt)
- Modify: [`README.md`](/tmp/itnewsletter-hn-og-image/README.md)
- Modify: [`tests/test_build_archive_site.py`](/tmp/itnewsletter-hn-og-image/tests/test_build_archive_site.py)

- [ ] Add `Pillow` to `requirements.txt` so the Vercel build environment can render PNG files.
- [ ] Add a short README note that HN detail pages now get build-time OG preview PNGs while GeekNews and other sources continue using the shared icon.
- [ ] Add a short README note that the renderer uses bundled fonts for deterministic output across local and Vercel builds.
- [ ] Review `tests/test_build_archive_site.py` for any duplicated assertions introduced during the first TDD pass and simplify them without weakening coverage.
- [ ] Run `python3 -m unittest tests.test_build_archive_site -v`.
- [ ] Confirm the broader build-site test module passes.
- [ ] Commit the dependency and documentation updates.

## Chunk 5: End-To-End Verification And PR Prep

### Task 5: Verify generated output and package the branch for review

**Files:**
- Modify: [`scripts/build_archive_site.py`](/tmp/itnewsletter-hn-og-image/scripts/build_archive_site.py)
- Modify: [`site/templates/detail.html`](/tmp/itnewsletter-hn-og-image/site/templates/detail.html)
- Modify: [`tests/test_build_archive_site.py`](/tmp/itnewsletter-hn-og-image/tests/test_build_archive_site.py)
- Modify: [`requirements.txt`](/tmp/itnewsletter-hn-og-image/requirements.txt)
- Modify: [`README.md`](/tmp/itnewsletter-hn-og-image/README.md)

- [ ] Run `python3 scripts/build_archive_site.py`.
- [ ] Confirm `dist/og/hn/` exists and contains the expected PNG for at least one HN fixture or live item.
- [ ] Open one generated HN detail page HTML and confirm the head metadata points to `/og/hn/<detail-slug>.png` with `summary_large_image`.
- [ ] Open one generated non-HN detail page HTML and confirm it still points to `/img.icons8.png` with `summary`.
- [ ] Confirm the detail-page body markup still has no inserted OG preview image block.
- [ ] Run `git status --short` and verify only the planned files plus generated local `dist/` output changed.
- [ ] Commit any final cleanup if verification required a code adjustment.
- [ ] Push `feat/hn-og-ai-preview`.
- [ ] Open a PR that calls out three things explicitly: HN-only scope, no visible detail-page image change, and fallback-to-default-icon behavior on render failure.

## Verification Commands

- Focused test: `python3 -m unittest tests.test_build_archive_site.BuildSiteTests.test_build_site_generates_detail_pages_and_safe_fallback -v`
- Build-site test module: `python3 -m unittest tests.test_build_archive_site -v`
- Static build: `python3 scripts/build_archive_site.py`

## Risks To Watch During Execution

- Pillow text measurement can vary if the wrong font file loads; verify the bundled font path early.
- Korean translated titles and long English originals may need different wrap limits; keep truncation deterministic.
- The build currently rewrites `dist/` wholesale, so OG asset generation must happen after `shutil.copytree(SITE_SRC, DIST_DIR)` recreates the output tree.
- Do not let HN-only metadata branching leak into GeekNews or other English detail pages.
