# Hacker News OG Preview Image Design

## Goal

Add automatic Open Graph preview images for Hacker News archive detail pages without changing the visible detail-page UI.

The new system should:

- generate a share image only for `Hacker News Frontpage (HN RSS)` detail pages
- keep the generated image out of the detail-page body
- replace the current shared-icon `og:image` with an article-specific preview image for HN pages only
- keep non-HN pages on the current default icon path
- run entirely at build time with static assets in `dist/`

## Why This Exists

The current detail pages already publish OG metadata, but every page points to the same small shared icon.

That causes two problems:

- shared links do not visually distinguish one Hacker News story from another
- the current preview does not communicate the article headline or the fact that the page came from Hacker News

The user wants a safer first step than AI image generation:

- no runtime image model
- no API cost
- no image shown inside the actual detail page
- only the link-preview image should change

## Approved Product Decisions

The following decisions were explicitly approved during brainstorming:

- target source: `Hacker News Frontpage (HN RSS)` only
- output type: text-based generated image, not AI-generated artwork
- card contents: translated title + original title
- source treatment: include a small `Hacker News` label
- visual direction: brand-forward card based on the current site palette
- delivery surface: OG/Twitter metadata only, not visible page content
- initial implementation: build-time PNG generation, not SVG-only and not browser screenshot rendering

## Scope

### In Scope

- build-time generation of `1200x630` PNG OG cards for HN detail pages
- static output under `dist/`
- detail-page metadata changes for HN entries
- HN-only `twitter:card` upgrade to `summary_large_image`
- safe fallback to the current default icon when OG card generation cannot run
- regression tests covering HN/non-HN behavior
- README note documenting the new dependency and behavior

### Out Of Scope

- AI image generation APIs or local image models
- OG image generation for GeekNews
- OG image generation for non-HN English sources
- displaying generated images inside the detail page
- adding per-item dates, points, comment counts, or summary copy to the card
- runtime OG rendering endpoints
- caching or incremental regeneration optimizations beyond normal build output

## Product Intent

The preview image should feel like a branded editorial card rather than a decorative poster.

It should:

- make the headline readable at a glance in chat previews
- preserve continuity with the existing site visual language
- make the HN origin obvious without overpowering the headline

It should not:

- look like generic AI art
- introduce extra information density
- make the site feel visually inconsistent with current archive pages

## Architecture Overview

The feature should be implemented inside the existing Python archive build pipeline.

High-level flow:

1. load archive items from `data/news.json`
2. identify items that qualify as HN detail pages
3. generate one PNG preview image per qualifying HN item
4. write those images into the static build output
5. point that item's `og:image` and `twitter:image` metadata to the generated PNG
6. keep all other items on the current default icon path

This keeps the system:

- static
- deterministic
- deployable through the current Vercel build flow
- independent of runtime services

## Output Contract

### Target Pages

An item qualifies for generated OG image output when all of the following are true:

- `source == "Hacker News Frontpage (HN RSS)"`
- a `detail_slug` exists
- at least one title string exists for rendering

### Asset Path

Generated images should use a stable static path:

- `dist/og/hn/<detail-slug>.png`

The public URL should resolve from `SITE_BASE_URL`, for example:

- `https://itnewsletter.vercel.app/og/hn/<detail-slug>.png`

### Metadata Behavior

For HN detail pages:

- `og:image` uses the generated PNG
- `twitter:image` uses the generated PNG
- `twitter:card` becomes `summary_large_image`
- OG width/height should reflect `1200x630`

For non-HN detail pages:

- keep the existing shared icon as `og:image`
- keep the current Twitter card behavior unless a shared template cleanup is required for parameterization

## Card Composition

The generated image should follow the approved brand-forward direction.

### Visual Structure

- bright layered background based on the current site palette
- subtle brand shell/surface treatment, not a flat poster
- small brand lockup for `IT Dispatch Archive`
- small `Hacker News` source chip
- translated title as the dominant text block
- original title as secondary text beneath it

### Text Rules

- translated title is required when available and should render largest
- original title renders below it when it differs from the translated title
- if translated title is missing, fall back to original title as the primary line
- if original title is missing or identical, omit the secondary line
- clamp lines so text remains readable in a `1200x630` card
- truncate overflow with ellipsis rather than shrinking into unreadable text

### Explicit Exclusions

Do not render:

- summary text
- HN points
- HN comment count
- publication date
- thumbnails from the source article

## Data Flow

### Build Inputs

Required input fields come from the existing archive item:

- `source`
- `detail_slug`
- `translated_title`
- `title`

### Build Steps

1. archive items are normalized as they are today
2. HN items are filtered for OG image eligibility
3. the builder renders each eligible card to PNG
4. the builder returns the public asset URL for use in detail-page substitution
5. detail-page rendering receives per-item OG metadata instead of always using the shared icon

### Template Implication

The detail template currently accepts one shared `og_image_url`.

This feature requires item-level metadata substitution for at least:

- `og_image_url`
- `twitter_card`
- `og_image_width`
- `og_image_height`

## Dependency Choice

The implementation may add a single Python image-rendering dependency, most likely `Pillow`.

Reasoning:

- PNG output is the safest path for link-preview compatibility
- the existing build pipeline is already Python-based
- this avoids introducing a browser runtime or client-side rendering dependency

No additional frontend or runtime service dependency should be introduced for this feature.

## Failure Handling

The build must stay resilient.

Rules:

- if card generation fails for a specific HN item, do not fail the whole site build
- instead, log the issue and fall back that item to the existing shared icon metadata
- if output directory creation fails globally, the build may fail because static output is no longer trustworthy
- missing optional text fields should degrade gracefully through title fallback rules

This keeps the feature reversible and low-risk for publishing.

## Files Expected To Change

Primary:

- `scripts/build_archive_site.py`
- `site/templates/detail.html`
- `tests/test_build_archive_site.py`
- `requirements.txt`
- `README.md`

Possible support files:

- static font or asset helpers only if the image renderer needs bundled resources

## Verification

Implementation planning should preserve the following checks:

### Automated Tests

- HN detail pages emit a generated OG image path
- non-HN detail pages still emit the default shared icon path
- HN detail pages use `summary_large_image`
- non-HN detail pages do not accidentally switch to HN-specific metadata
- generated files are written to the expected `dist/og/hn/` location
- detail-page HTML does not gain visible image markup in the body

### Manual Verification

- build the site locally
- open a generated HN detail page and confirm no new image appears in page content
- inspect the built HTML and confirm HN metadata points to the generated PNG
- confirm the generated PNG exists and has the intended dimensions

## Planning Notes

This spec is intentionally narrow.

The next planning step should focus on:

- image rendering helper design inside `build_archive_site.py`
- metadata parameterization in the detail template
- regression test coverage
- minimal documentation updates

It should not expand into a broader share-preview redesign or a generic OG image platform.
