# Discord Push Preview Design

## Background
- The current Discord batch message starts each item with source labels, summary headings, preview text, and links.
- On iOS push notifications, that structure spends too much space on non-click-driving text before the actual article titles appear.
- The user wants the push preview to show the most important headlines first while keeping the in-channel detail blocks below.

## Goal
- Show the top 3 selected article titles at the top of the Discord message.
- Keep the existing per-item blocks below the preview section so channel readers still get the current detail format.
- Preserve the existing batch size fallback logic and Discord message length guardrails.

## Non-Goals
- Do not add a Discord-specific push payload separate from the message body.
- Do not change prioritization, selection order, or link targets.
- Do not remove the existing article block format below the preview section.

## Approach
1. Add a small preview section immediately after the batch header.
2. Build the preview from the first 3 selected items in batch order.
3. Render each preview line as `- <title>` using `translated_title` when available.
4. Leave the existing numbered per-item blocks unchanged below the preview section.
5. Let the existing mode fallback (`full_summary`, `compact_summary`, `titles_only`) continue to measure the full message length including the new preview section.

## Formatting
- Header example: `이번 배치 뉴스 5건`
- Preview example:
  - `- ...`
  - `- ...`
  - `- ...`
- Then keep the current blank line spacing and detailed item blocks.

## Validation
- Confirm only up to 3 preview titles are rendered.
- Confirm translated titles are preferred in the preview.
- Confirm the detailed blocks still appear below the preview section.
- Confirm the batch selector still falls back safely when the message gets long.
