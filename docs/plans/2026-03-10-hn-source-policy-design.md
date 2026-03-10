# Hacker News Source Policy Design

## Goal
- Surface more high-signal Hacker News frontpage items in the Discord batch.
- Keep lazy detail generation safe by allowing HN only through curated downstream domains.
- Reduce low-value batch noise from Product Hunt.

> Note: this policy was later superseded by the HN API-native briefing path in
> `2026-03-10-hn-api-briefing-design.md`, which allows HN detail briefing from
> HN story/comment context without relying on downstream article-domain allowlists.

## Decisions
- Disable `Product Hunt Feed` by default.
- Raise the `Hacker News Frontpage (HN RSS)` source priority boost.
- Add HN-specific taxonomy boosts for:
  - `practical_tech`
  - `tools_agents`
  - `strategy_insight`
- Add a source-specific lazy-detail domain override for HN instead of allowing the whole source.
- Broaden the HN override list with more engineering-blog and open-source domains seen in the archive.

## Safety Rules
- HN lazy detail remains deny-by-default.
- Only HN links whose final domain matches the curated override list can trigger lazy detailed briefing.
- Global lazy-detail rules for direct sources remain unchanged.

## Files
- `config/sources.yaml`
- `config/taxonomy.yaml`
- `config/lazy_detail_allowlist.json`
- `scripts/build_archive_site.py`
- `api/_lib/lazy-detail-config.mjs`
