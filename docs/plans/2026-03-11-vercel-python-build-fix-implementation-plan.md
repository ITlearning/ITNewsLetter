# Vercel Python Build Fix Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix the Vercel production build so dependency installation works in the managed Python environment.

**Architecture:** Replace the direct `pip install` command in `vercel.json` with a repo-local virtualenv bootstrap, then run the site build with that virtualenv's Python interpreter. Keep the rest of the Vercel output contract unchanged.

**Tech Stack:** Vercel project configuration, Python virtualenv

---

## File Structure

- Modify: [`vercel.json`](/Users/tabber/ITNewsLetter/vercel.json)

## Chunk 1: Virtualenv-Based Install

### Task 1: Update the Vercel commands

**Files:**
- Modify: [`vercel.json`](/Users/tabber/ITNewsLetter/vercel.json)

- [ ] Replace the direct `pip install` command with `python3 -m venv .vercel-venv`.
- [ ] Install requirements with `.vercel-venv/bin/pip`.
- [ ] Run the build with `.vercel-venv/bin/python`.

## Chunk 2: Verification

### Task 2: Validate the config locally

**Files:**
- Modify: [`vercel.json`](/Users/tabber/ITNewsLetter/vercel.json)

- [ ] Validate the JSON syntax.
- [ ] Run the virtualenv install command locally.
- [ ] Run the build command locally and confirm `dist/` is produced.
