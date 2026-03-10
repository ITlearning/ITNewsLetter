# Lazy Detail Summary Reveal Design

## Goal
- Make the generated detail briefing feel intentionally "AI-assisted" at the moment it appears.
- Avoid permanent flashy motion after the content settles.

## Decision
- Apply a one-time reveal animation only when the lazy detail summary arrives.
- Do not animate while the request is still loading.

## Motion Rules
- The loaded summary appears paragraph by paragraph.
- Each paragraph uses a short stagger delay.
- While entering, the text itself carries a rainbow gradient sweep.
- At the same time, each paragraph fades in and settles from a slight right offset.
- After the animation finishes, the text returns to the normal article color.

## Accessibility
- Respect `prefers-reduced-motion`.
- In reduced-motion mode, render the summary immediately without gradient sweep.

## Files
- `site/detail.js`
- `site/detail.css`
