# Web Archive List Layout Design

## Goal

- Reduce the oversized hero treatment at the top of the archive page.
- Keep the archive stats visible.
- Replace the grid-style news cards with a denser single-column list.

## Decision

- Use a compact `topbar + stats strip + filters + list` structure.
- Keep the archive name in the top bar only.
- Keep `Archive / Sources / Updated` stats below the top bar.
- Render archive items as a single-column list with a small metadata column and a larger content column.

## Why

- The previous hero consumed too much vertical space before the news list started.
- The grid layout reduced scanability for archive use, especially when comparing dates, sources, and slot labels.
- A list layout better fits chronological browsing and filtering.

## Scope

- Update `site/index.html`
- Update `site/styles.css`
- Keep `site/app.js` data rendering logic mostly unchanged, with only container naming aligned to the new layout
