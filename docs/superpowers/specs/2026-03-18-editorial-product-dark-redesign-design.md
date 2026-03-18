# Editorial Product Dark Redesign

## Goal

Redesign the public archive so it feels like one premium product instead of a stack of unrelated archive widgets.

The new system should:

- make the homepage lead with a strong brand/product message
- keep the archive fast to scan and obviously useful
- make detail pages feel calmer and more readable
- turn topic pages into product-style briefing indexes rather than leftover hubs
- unify home, detail, and topic pages under one dark premium design language

## Why This Exists

The current site is functional, but the visual system still reads like a mix of utility archive patterns and generic AI-era section cards.

Current issues:

- typography is too flat and too uniform
- homepage modules compete with each other instead of establishing one clear hierarchy
- `이번 배치 브리핑` and `주간·월간 토픽` occupy too much homepage attention for their actual value
- the page relies too heavily on rounded translucent cards
- the detail page has useful information, but it does not yet feel like a premium reading surface
- the topic pages work, but do not yet feel like first-class product screens

The redesign should preserve the site's utility while making it feel intentional, premium, and consistent.

## Product Intent

The site should feel like a product that continuously indexes and explains IT shifts.

It is not:

- a glossy AI landing page
- a consumer magazine
- a dashboard with dense control surfaces

It is:

- a product-shaped archive
- a dark premium signal index
- a place where daily IT movement is stored, organized, and made easier to read

Brand voice:

- product-oriented
- precise
- restrained
- confident without sounding promotional

## Scope

### In Scope

- homepage redesign
- detail page redesign
- topic page redesign
- shared visual system across all three page types
- homepage information architecture cleanup
- improved typography, surfaces, controls, motion, and hierarchy
- reuse of existing archive data and existing Spotlight/detail pipelines

### Out of Scope

- backend architecture changes unrelated to rendering
- account systems or personalization
- new data ingestion sources
- replacing the existing archive/filter model
- replacing the current lazy-detail queue model

## Design Principles

### 1. Editorial Product

Structure should behave like software.

Presence should feel like editorial design.

This means:

- bold but restrained hero typography
- clear information hierarchy
- fewer but better surfaces
- less visual chatter
- stronger vertical rhythm

### 2. Dark Premium, Not Neon AI

The system should use a deep navy-charcoal base, not pure black and not purple-blue AI gradients.

Rules:

- no purple glow aesthetic
- no over-saturated accent palette
- one electric-cool accent only
- highlights should come from hierarchy and spacing first, color second

### 3. One Product, Three Screens

Home, detail, and topics should clearly belong to the same system.

Shared traits:

- same typography rules
- same dark surface language
- same border and shell logic
- same motion rhythm
- same control styling

### 4. Utility Must Survive the Redesign

The archive is still the core product.

The redesign must not make search, scanning, or clicking slower or less obvious.

## Visual System

### Color

Base palette:

- background: dark navy-charcoal, not pure black
- surfaces: slightly lifted blue-charcoal layers
- text: warm white for primary, softened slate-white for secondary
- accent: one restrained electric blue

Surface logic:

- large sections use outer shell + inner core treatment when elevation matters
- routine content rows should rely on spacing and separators before full card treatment
- shadows should be diffused and tinted, never thick or muddy

### Typography

The redesign should move away from a single utilitarian font feeling.

Rules:

- headline font: premium sans with stronger personality and tighter tracking
- body/UI font: clean, highly readable sans
- mono/meta font: tabular or mono treatment for metrics where useful
- no generic UI typography feeling
- no serif for primary product surfaces

Typography behavior:

- large headlines should feel deliberate and compressed
- labels and microcopy should use smaller tracked text
- long paragraphs should stay narrow and highly readable

### Shapes and Surfaces

Rules:

- fewer generic glass cards
- large containers can use soft squircle radii
- inner elements use tighter radii
- buttons should feel machined, not bubbly
- lists should often read as structured records, not repeating marketing cards

### Motion

Motion should feel expensive but controlled.

Allowed behavior:

- slow fade-up on section entry
- subtle press feedback on buttons
- controlled Spotlight transitions
- quiet hover response on cards and list rows

Disallowed behavior:

- constant ornamental animation
- noisy glowing effects
- motion that competes with reading

## Homepage Redesign

## Role

The homepage should answer:

- what this product is
- why the archive is valuable
- what to look at first
- how to move into the archive immediately

## Homepage Information Architecture

Order:

1. brand/product hero
2. live archive metrics
3. AI Spotlight
4. archive controls
5. archive list

Removed from homepage prominence:

- `이번 배치 브리핑`
- `주간·월간 토픽`

`/topics/` remains part of the product, but it should not dominate the homepage.

## Homepage Hero

The hero is the primary identity surface.

Requirements:

- lead with the product message, not the search box
- use one dominant headline and one supporting paragraph
- present 1-2 clear CTAs
- pair the copy with live operational trust signals

The hero should feel like a product declaration, not a marketing stunt.

## Live Metrics

The hero support block should use live metrics rather than screenshots or sample cards.

Metrics should include:

- archive count
- source count
- last updated time

The block should signal trust and system activity, not just decorative stats.

## AI Spotlight

`AI Spotlight` remains a first-class module, but it should stay outside the hero.

Role:

- the one featured editorial intelligence surface near the top
- visually connected to the hero, but clearly a separate module

Requirements:

- independent section below hero
- large featured card treatment
- controlled navigation between modules
- stronger internal hierarchy than the archive list

## Archive Controls

Search and filters should look like product controls, not a generic filter bar.

Requirements:

- slimmer and more refined shell
- clearer field hierarchy
- consistent active and focus states
- stronger relationship to the archive list below

## Archive List

The list should shift away from a generic article-card look and toward a premium indexed-record feel.

Requirements:

- clearer hierarchy between meta, title, summary, and actions
- less visual card boxing
- stronger row rhythm
- actions remain obvious without dominating the row

## Detail Page Redesign

## Role

The detail page is the core reading surface.

The user should feel that the article, the briefing, and the support cards all belong to one calm reading experience.

## Structure

Order:

1. dark masthead
2. article meta
3. headline and short setup
4. primary actions
5. ad shell
6. detailed briefing
7. supporting cards (`왜 중요한가`, `HN 반응`, Spotlight linkages when relevant)
8. related article area

## Detail Masthead

The detail top area should be much more restrained than the homepage hero.

Requirements:

- strong headline
- thin, precise metadata row
- compact action area
- more whitespace around the reading column

## Briefing Surface

The briefing is the primary content block.

Requirements:

- narrower, more readable content measure
- better spacing between paragraphs
- less “widget” feeling
- visual weight clearly above all support modules

## Supporting Cards

`왜 중요한가`, `HN 반응`, and Spotlight-linked context should remain below the briefing.

They should be:

- visually lighter than the briefing
- still clearly part of the same system
- easier to skim in sequence

## Topic Page Redesign

## Role

Topic pages should feel like structured briefing indexes, not leftover landing pages.

## Structure

Order:

1. topic masthead
2. period + scope controls
3. core briefing summary
4. related article index

## Topic Character

Topic pages should sit between home and detail:

- more structured than detail
- less promotional than home
- more index-like than the current topic hub feel

Requirements:

- clear topic title and short explanatory setup
- refined period switching
- compact but premium list of related articles

## Existing Data and Rendering Model

This redesign should preserve the current data model wherever possible.

Keep:

- existing archive payload structure
- existing Spotlight data
- existing lazy-detail queue model
- existing topic digest data model

The redesign is primarily a rendering and interaction-system rewrite, not a product-logic rewrite.

## Implementation Boundaries

Use the existing stack:

- static HTML templates
- vanilla CSS
- vanilla JS

Do not:

- migrate frameworks
- add unnecessary frontend libraries
- introduce animation libraries unless they are strictly justified and already available

## Testing and Validation

Minimum validation:

- homepage renders with missing optional modules hidden cleanly
- detail pages remain readable with and without support cards
- topic pages render with different digest volumes
- archive filtering/search still works unchanged
- responsive layout holds at mobile, tablet, and desktop widths
- static build continues to pass

Design validation:

- home, detail, and topic visually read as one product
- hero and Spotlight are clearly separate
- the archive remains faster to scan, not slower
- the detail page feels calmer than the homepage
- topic pages feel promoted to first-class product surfaces

## Success Criteria

The redesign succeeds when:

- the site immediately feels more premium and less generic
- the homepage has one obvious top-level story: the product itself
- Spotlight feels important, but not jammed into the hero
- archive scanning remains easy
- detail reading quality visibly improves
- topic pages feel intentional enough to keep
