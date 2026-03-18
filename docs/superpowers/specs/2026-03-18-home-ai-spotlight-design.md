# Home AI Spotlight and Editorial Signal Modules

## Goal

Rework the archive homepage so it feels more intentional, more revisit-worthy, and less like a stacked list of utility sections. The new top-level experience should promote one strong AI-generated module at a time while keeping the archive fast to scan.

This design also defines three follow-on editorial AI modules that can share one rendering shell and one queue/cache pipeline:

- `이번 주 조용히 커지는 주제`
- `HN 댓글이 가장 갈린 기사`
- `이번 주 이상 신호`

## Why This Exists

The current homepage has sections the owner does not use (`이번 배치 브리핑`, `주간/월간 토픽`). They add weight but do not create strong revisit behavior or a memorable identity.

The desired direction is:

- keep the archive useful and searchable
- make the homepage feel editorial, not generic AI SaaS
- let one strong AI module lead the page
- keep everything fully automatic with queue + cache behavior
- avoid user accounts and server-side personalization

## Product Intent

The homepage should answer:

- what is the one thing worth looking at right now?
- why should I come back tomorrow?
- what makes this site feel different from a plain archive?

The design direction is a hybrid:

- headline and presence from editorial/magazine references
- information discipline from product interfaces
- structured disagreement framing for HN discussion modules
- minimal reliance on glossy AI-style gradients or blob aesthetics

## Scope

### In Scope

- remove homepage exposure of `이번 배치 브리핑`
- remove homepage exposure of `주간/월간 토픽`
- keep `/topics/` pages alive, but do not feature them on the homepage
- add a single `AI Spotlight` module near the top of the homepage
- support 3 Spotlight card types with one shared shell
- define data model, queue model, scoring, fallback, and display behavior
- define light linkage from detail pages back into the Spotlight system

### Out of Scope

- user login
- server-side personalization
- recommendation systems based on account identity
- replacing the existing archive list/search/filter model
- full implementation of the three editorial modules in this spec
- redesigning the whole site outside the homepage and related detail-callout surfaces

## Homepage Information Architecture

Homepage order:

1. Brand and archive stats
2. `AI Spotlight`
3. Search/filter controls
4. Full archive list

Removed from homepage:

- `이번 배치 브리핑`
- `주간/월간 토픽`

Retained elsewhere:

- `/topics/` remains accessible by direct URL and any existing non-home links

## AI Spotlight Module

### Role

`AI Spotlight` is the homepage's single featured AI surface. It should feel like today's most interesting editorial module, not a utility widget.

### Interaction Model

- show one primary card at a time
- allow left/right navigation or dot navigation to inspect other available cards
- always choose one default card automatically
- if the strongest candidate is weak, fall back to the next-best card rather than hiding the module

### Selection Policy

Default selection should be based on current recency and available signal quality, not per-refresh randomness.

The system should:

1. generate one candidate from each module family
2. assign each candidate a quality score
3. choose the highest scoring candidate as today's featured Spotlight
4. use the next-best candidate if the top candidate fails quality thresholds
5. keep the chosen card stable for the cache window instead of changing every visit

This keeps the homepage coherent while still letting the user browse the other two cards.

## Shared Spotlight Card Shell

All three modules should render inside one shared outer shell:

- eyebrow/label
- dominant title
- one short explanatory line
- compact supporting structure
- one clear CTA
- next/previous navigation affordance

The shell should feel editorial first and app-like second:

- big typographic moment
- restrained controls
- dense enough to be useful
- no over-decorated AI-dashboard visuals

## Module 1: 이번 주 조용히 커지는 주제

### Purpose

Highlight a topic that is not yet the dominant story of the week, but is starting to recur across recent items.

### Visual Direction

- strongest title presence of the three modules
- large `조용히 커지는 주제` heading
- supporting topic-specific label below or adjacent
- short list of 2-3 concrete supporting signals beneath
- magazine-like composition rather than a feature grid

### Data Inputs

- recent archive items, defaulting to the last 7 days
- slot labels
- extracted topics/entities/keywords
- cross-source recurrence
- relation density between recent items

### Output Shape

- `topic_name`
- `summary_line`
- `signals[]` (2-3 short bullets)
- `related_item_ids[]`
- `score`

### Scoring Heuristic

Reward:

- repeated appearance across multiple items
- recurrence across more than one source
- topics that are increasing but not already saturating the feed

Penalize:

- one-off hype
- already obvious top story themes
- vague topics with poor naming clarity

## Module 2: HN 댓글이 가장 갈린 기사

### Purpose

Surface the article whose HN discussion shows the clearest internal split, not just the highest comment count.

### Visual Direction

This should be a structured editorial disagreement card, not a loud red-vs-blue gimmick.

Layout:

- left column: opposition
- center column: issue / what the argument is about
- right column: support

Color behavior:

- left can use restrained red gradients or warm tones
- right can use restrained blue gradients or cool tones
- center remains neutral and readable

### Data Inputs

- items with HN story ids
- stored HN reaction summaries
- comment count
- extracted pro/con argument density

### Output Shape

- `item_id`
- `headline`
- `issue_title`
- `opposition_summary`
- `support_summary`
- `score`

### Scoring Heuristic

Reward:

- both sides are clearly represented
- the disagreement is understandable in one glance
- the article itself is meaningful enough to click through

Penalize:

- high comments but no real split
- low-signal argument summaries
- controversy driven purely by noise or jokes

## Module 3: 이번 주 이상 신호

### Purpose

Expose weak but persistent signals that do not yet look like mainstream categories but keep appearing across the archive.

### Visual Direction

This module can feel more experimental than the others, but still should not drift into generic AI visual tropes.

Desired cues:

- black-to-white gradient field
- strong poster-like heading
- compact signal blocks or labels
- labs-like tone without looking unfinished

### Data Inputs

- recent archive items
- weak recurring entities/terms
- source diversity
- distance from existing stronger topic clusters

### Output Shape

- `signal_title`
- `summary_line`
- `signals[]` (3 compact sub-signals)
- `related_item_ids[]`
- `score`

### Scoring Heuristic

Reward:

- patterns recurring across multiple items
- patterns not already captured by dominant topic summaries
- patterns that feel surprising but nameable

Penalize:

- random coincidence
- overly broad trend labels
- weak evidence sets

## Detail Page Integration

The detail page should not repeat the full homepage Spotlight experience.

Instead, use lightweight linkage:

- if the current article is the representative item for one Spotlight module, show a thin contextual callout
- if the article belongs to a Spotlight cluster, show a small connection block
- keep existing briefing flow primary

Preferred detail order:

1. briefing
2. why-it-matters / HN reaction / existing analysis cards
3. thin Spotlight linkage block when relevant
4. related items

This preserves readability and avoids turning the detail page into another homepage.

## Generation and Caching Model

Use the same operating philosophy as the existing lazy detail pipeline:

1. read cache first
2. if missing or stale, enqueue generation
3. Mac Studio Codex worker generates output
4. store normalized result
5. future visits reuse cache

### Cache Granularity

- one cache entry per module family result
- one cache entry for the chosen homepage featured Spotlight
- TTL should align to editorial freshness, likely daily or per-dispatch-window

### Queue Behavior

- homepage can display cached data immediately
- if module data is missing, enqueue behind the scenes
- a low-quality or unavailable module should not block the page
- fallback chooses the next-best candidate

## UX Quality Constraints

These constraints are design-critical:

- homepage must become simpler, not more crowded
- the Spotlight shell should feel premium and editorial, not like a dashboard widget
- cards must share a shell but preserve distinct personalities
- homepage should still feel good if only one of the three modules has high-quality data
- the absence of a strong module should degrade gracefully

## Failure Handling

### Missing Data

- if one module has no candidate, exclude it from the carousel
- if two modules fail, show the remaining one as the default Spotlight without dead controls
- if all modules fail, hide Spotlight entirely and fall back to the clean archive homepage

### Low Confidence Output

- if generated titles or summaries are too vague, do not publish them into the Spotlight slot
- fallback to another module rather than exposing low-confidence editorial output

### Worker Lag

- homepage should never block on generation
- it should show the latest valid cached Spotlight until a newer one is ready

## Testing Strategy

### Data-Level Tests

- candidate scoring produces deterministic results for fixed fixture inputs
- fallback picks the next-highest valid module
- low-quality candidates are excluded

### Build Tests

- homepage payload includes Spotlight only when valid data exists
- each module output shape serializes correctly into build artifacts
- detail pages render contextual linkage only when relevant

### UX Tests

- homepage still reads cleanly with zero, one, two, or three valid modules
- Spotlight controls do not appear broken when only one module is present
- detail page linkage stays lighter than the main briefing sections

## Implementation Sequence

Recommended order:

1. homepage cleanup and shared Spotlight shell
2. `이번 주 조용히 커지는 주제`
3. `HN 댓글이 가장 갈린 기사`
4. `이번 주 이상 신호`

This order produces value early while building toward the more experimental Labs-like module last.

## Open Decisions Resolved in This Spec

- no server-side personalization
- no account system
- homepage keeps one featured Spotlight card rather than multiple big sections
- featured card is selected by recency/quality scoring, not per-refresh randomness
- low-quality top choice falls back to the next-best module
- `/topics/` remains alive but is removed from homepage emphasis

## Success Criteria

The feature is successful if it creates:

- stronger revisit motivation
- a clearer editorial identity
- modules distinctive enough to be remembered and shared

It does not need to optimize for broad personalization or heavy user modeling.
