# Humanized Briefing Markdown Design

## Goal
- Make detailed briefings easier to scan and read without making them shorter.
- Reduce AI-like Korean phrasing by embedding humanizer rules into the generation prompt.

## Decisions
- Keep a single OpenAI call per item.
- Continue storing `detailed_summary` as one string, but allow limited Markdown syntax inside it.
- Support a safe subset in the detail page renderer:
  - paragraphs
  - bullet lists (`- item`)
  - bold (`**text**`)
- Update prompt instructions so `detailed_summary` follows this structure:
  - short opening paragraph
  - 3-5 bullet points
  - closing paragraph about meaning or implications
- Apply humanizer rules in-prompt:
  - avoid comma-heavy sentences
  - avoid generic AI buzzwords
  - vary sentence rhythm
  - keep Korean phrasing direct and natural
  - preserve meaning and facts

## Non-Goals
- No second OpenAI pass for post-editing.
- No full Markdown support.

## Files
- `scripts/fetch_and_send.py`
- `api/_lib/lazy-detail-openai.mjs`
- `scripts/build_archive_site.py`
- `site/detail.js`
- `tests/test_fetch_and_send_enrichment.py`
