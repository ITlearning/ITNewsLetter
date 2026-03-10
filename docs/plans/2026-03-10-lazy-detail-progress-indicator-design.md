# Lazy Detail Loading Indicator Design

## Goal
- Make on-demand detail briefing visibly "alive" while the browser waits for the lazy summary API.
- Reduce ambiguity from a single static loading sentence.

## Decision
- Replace the progress rail with a simpler loading-focused pattern:
  - spinner
  - elapsed timer
  - loading note
  - summary skeleton blocks

## UX Rules
- Primary message:
  - `추가 브리핑을 불러오는 중입니다`
- Show elapsed time like `00:03`, `00:08`.
- Show a spinner so the request feels active.
- Replace the summary body with skeleton lines while the request is in flight.
- After ~8 seconds, show a slower-path hint:
  - `조금 더 걸리고 있습니다. 브라우저를 닫지 않아도 됩니다.`
- If the request fails or is unsupported, restore the original short summary.

## Non-Goals
- No real backend streaming progress yet.
- No percentage indicator.
- Success, unsupported, and failure states remain simple status messages.

## Files
- `site/templates/detail.html`
- `site/detail.css`
- `site/detail.js`
