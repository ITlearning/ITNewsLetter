# Lazy Detail Progress Indicator Design

## Goal
- Make on-demand detail briefing visibly "alive" while the browser waits for the lazy summary API.
- Reduce ambiguity from a single static loading sentence.

## Decision
- Replace the single loading sentence with a hybrid pattern:
  - 3-step progress rail
  - animated dots in the header
  - delayed note when the request takes longer than expected

## UX Rules
- Steps:
  - `요청 시작`
  - `원문 분석`
  - `브리핑 생성`
- The current step is highlighted.
- Completed steps turn green.
- A subtle animated dot cluster communicates that work is still active.
- After ~8 seconds, show a slower-path hint:
  - `조금 더 걸리고 있습니다. 브라우저를 닫지 않아도 됩니다.`

## Non-Goals
- No real backend streaming progress yet.
- No percentage indicator.
- Success, unsupported, and failure states remain simple status messages.

## Files
- `site/templates/detail.html`
- `site/detail.css`
- `site/detail.js`
