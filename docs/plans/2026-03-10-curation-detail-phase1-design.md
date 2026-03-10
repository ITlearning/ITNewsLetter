# Curation Detail Phase 1 Design

## Goal

Convert the current sent-news archive into a curation-oriented reading product without mirroring original article bodies.

Phase 1 adds:

- static detail pages for all sent news
- related article recommendations on detail pages
- a "today's curation" section on the archive list page

## Product Direction

- The archive is no longer only a search surface.
- The primary experience becomes `scan -> brief -> click through to source`.
- Detail pages are briefing pages, not replacement reading pages.

## Content Policy

- Do not scrape and store full article bodies from GeekNews or Korean news sources.
- Do not mirror original article text on the archive site.
- Store and show only:
  - source title
  - translated title
  - short summary
  - detailed summary
  - source/date/slot metadata
  - matched terms
  - original link
- English items may generate AI summaries at dispatch time.
- Korean and GeekNews items must not trigger new summary generation just for archive detail pages.

## Scope

### 1. Detail Pages

Create one static detail page per sent item.

Recommended path:

- `dist/news/<detail_slug>/index.html`

Detail page layout:

- translated title
- original title
- source, sent date, slot badge
- `detailed_summary` if present
- fallback to `short_summary` when `detailed_summary` is missing
- matched taxonomy terms
- strong primary CTA to original article
- previous/next article navigation
- 2-3 related articles

### 2. Related Articles

Detail pages show a small related section.

Selection rules:

- first priority: same primary slot
- second priority: overlapping matched terms
- third priority: same source
- exclude current item
- cap at 3 items

This should be computed during site build, not stored permanently in `data/news.json`.

### 3. Today's Curation

Add a top section on the archive list page that highlights the most recent dispatch batch.

Section contents:

- label: today's curation
- recent sent items from the latest dispatch window
- compact list layout, separate from the full archive list
- CTA to each detail page

This section should help the site feel editorial instead of only archival.

## Data Model

Extend stored archive item fields with:

- `detail_slug`
- `detailed_summary`
- `is_english_source`

Build-time derived fields:

- `detail_url`
- `related_items`
- `is_today_pick`

Fallback behavior:

- if `translated_title` missing, use original title
- if `detailed_summary` missing, use `short_summary`
- if both summaries missing, show minimal metadata and source CTA only

## Generation Timing

### Dispatch Time

For English items only:

- generate `translated_title`
- generate `short_summary`
- generate `detailed_summary`

For Korean and GeekNews items:

- do not add new GPT calls for detail pages
- reuse existing stored metadata and summaries only

### Site Build Time

- build archive index page
- build per-item detail pages
- compute related article links
- compute today's curation section

## UI Direction

Use a reading-first editorial style, but avoid oversized hero treatments.

Recommended visual direction:

- compact top bar
- paper-like light background
- dense but calm typography
- stronger hierarchy on detail pages than on list pages
- minimal motion

List page:

- top bar
- stats strip
- today's curation
- filters
- full archive list

Detail page:

- narrow reading column
- metadata rail or header row
- clear source CTA
- related articles at the bottom

## Non-Goals

- no full-text mirroring
- no article body scraping pipeline
- no comments
- no user accounts
- no analytics dashboard in phase 1

## Error Handling

- if detail build input is missing required identifiers, skip page generation and log the item id
- if `detailed_summary` is absent, fallback to `short_summary`
- if related article scoring finds nothing, hide the section cleanly
- if today's curation cannot be derived, hide the section and keep the archive list functional

## Testing

- verify detail pages are generated for all archive items
- verify English items show `detailed_summary` when present
- verify Korean and GeekNews items fallback correctly
- verify related article selection excludes the current item
- verify latest dispatch items appear in today's curation
- verify mobile layout at 375px and desktop layout at 1440px

## Implementation Order

1. extend stored data model for detail fields
2. generate static detail pages in the archive build script
3. add today's curation section to the list page
4. add related article logic and UI
5. refine navigation and fallback states
