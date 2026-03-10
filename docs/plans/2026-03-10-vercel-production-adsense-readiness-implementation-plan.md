# Vercel Production AdSense Readiness Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the archive deployable on a stable Vercel production domain and publish crawler-readable root files needed for AdSense verification.

**Architecture:** Keep the existing Python static-site build flow and declare Vercel's install, build, and output settings in `vercel.json`. Add `site/robots.txt` so the existing `site -> dist` copy step publishes the crawler policy file without changing the build script.

**Tech Stack:** Vercel project configuration, static HTML files, Python unit tests

---

## File Structure

- Create: [`vercel.json`](/Users/tabber/ITNewsLetter/vercel.json)
- Create: [`site/robots.txt`](/Users/tabber/ITNewsLetter/site/robots.txt)
- Modify: [`tests/test_build_archive_site.py`](/Users/tabber/ITNewsLetter/tests/test_build_archive_site.py)

## Chunk 1: Vercel Build Configuration

### Task 1: Commit the production build settings to the repo

**Files:**
- Create: [`vercel.json`](/Users/tabber/ITNewsLetter/vercel.json)

- [ ] Add a Vercel config with the root build command and `dist` output directory.
- [ ] Keep the configuration compatible with the existing `api/` directory and static `dist/` output.

## Chunk 2: Crawler Access File

### Task 2: Publish a root robots policy

**Files:**
- Create: [`site/robots.txt`](/Users/tabber/ITNewsLetter/site/robots.txt)

- [ ] Add a minimal allow-all robots policy.
- [ ] Rely on the existing `shutil.copytree(SITE_SRC, DIST_DIR)` build step to publish it at the root.

## Chunk 3: Verification

### Task 3: Extend build-output tests

**Files:**
- Modify: [`tests/test_build_archive_site.py`](/Users/tabber/ITNewsLetter/tests/test_build_archive_site.py)

- [ ] Assert `dist/robots.txt` exists after the build.
- [ ] Assert the published file allows crawler access.
- [ ] Run the relevant unit test file.
