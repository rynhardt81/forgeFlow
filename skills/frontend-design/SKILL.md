---
name: frontend-design
description: Design direction for building distinctive, intentional UI — aesthetic choices, typography, color, motion — instead of templated defaults. Trigger phrases — design this page, make it look good, UI polish, visual design, looks generic. NOT FOR component data/state logic, or for picking from the design catalog (use /ui-ux-pro-max for searchable styles/palettes/font pairings).
---

# Frontend Design

This is a routing card, not a vendored design course. Anthropic's full `frontend-design` skill ships as a first-party Claude Code plugin — if it's installed in your environment, invoke it and stop reading here. What follows is the self-contained fallback for bare installs.

## Core discipline (fallback)

1. **Pick one aesthetic direction and commit** — name it in a sentence ("dense engineering console", "warm editorial print") before touching code. Templated output comes from skipping this step.
2. **Typography does most of the work.** One display face + one text face maximum; set a real scale (e.g. 1.25 ratio) and stick to it. System-font stacks are a choice, not a default.
3. **Color: one dominant, one accent, neutrals earned.** Derive the palette from the aesthetic direction; check text contrast (WCAG AA minimum) before shipping.
4. **Spacing rhythm over decoration.** A consistent spacing scale (4/8px base) reads as polish; borders and shadows rarely do.
5. **States are design too** — empty, loading, error, and long-content states get designed, not discovered in production.
6. **Verify visually.** A design change is not done until you've looked at it rendered — screenshot the target route(s) at mobile and desktop widths. Judging CSS from source is forbidden.

## Catalog lookups

For concrete style references, palettes, and font pairings, use `/ui-ux-pro-max` — a searchable local database, no network needed.
