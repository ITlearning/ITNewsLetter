# Detail Initial Summary Reveal Design

## Goal
- Apply the same summary reveal animation to detail pages whose summary is already embedded in the initial HTML.

## Problem
- The rainbow reveal currently runs only when a lazy API response replaces the summary.
- Items with precomputed `detailed_summary` or non-lazy fallback summaries render as static text with no reveal.

## Decision
- Re-render the initial summary text with the existing animated paragraph markup on first load.
- Skip the initial reveal when a lazy detail request is about to replace the summary anyway.
- Keep `prefers-reduced-motion` behavior unchanged.

## Files
- `site/detail.js`
