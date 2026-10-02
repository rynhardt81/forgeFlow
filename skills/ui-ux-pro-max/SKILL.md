---
name: ui-ux-pro-max
description: "UI/UX design catalog and lookup. Provides concrete options when /frontend-design (or one of its interventions/<name>.md prescriptions) needs them — 67 styles, 96 palettes, 57 font pairings, 25 chart types, 10 stacks (HTML/Tailwind, React, Next.js, Vue, Svelte, SwiftUI, React Native, Flutter, shadcn/ui, Jetpack Compose). Use when the user wants to pick a style, palette, font pairing, chart type, or stack, or asks about specific aesthetics — glassmorphism, claymorphism, minimalism, brutalism, neumorphism, bento grid, dark mode. Integrates shadcn/ui MCP for component search. NOT FOR building a UI from scratch (use /frontend-design as the lead) or focused interventions on existing UI (use /frontend-design, which internally reads interventions/critique.md, polish.md, clarify.md, simplify.md, etc)."
---

# UI/UX Pro Max - Design Intelligence

Comprehensive design guide for web and mobile applications. Contains 67 styles, 96 color palettes, 57 font pairings, 99 UX guidelines, and 25 chart types across 10 technology stacks. Searchable database with priority-based recommendations. (Counts are the actual data rows in `data/*.csv` — recount there if the data changes.)

## Index

| File or section | Read when… |
|---|---|
| How to Use This Skill (below) | Every invocation — the step sequence |
| `scripts/search.py` | **Run** it — every query goes through this script |
| `SEARCH.md` | Persisting a design system (`--persist`, `--page`), choosing a `--domain` or `--stack`, output formats (`-f markdown`), search tips |
| `RULES.md` | Writing or reviewing UI code; the pre-delivery checklist before handing UI code over |

## Companion Skill: frontend-design

This skill provides *what* options exist; `/frontend-design` ([SKILL.md](../frontend-design/SKILL.md)) sets the aesthetic direction that picks among them. Use it first when building UI, then come here for concrete styles, palettes and pairings.

## When to Apply

Reference these guidelines when:
- Designing new UI components or pages
- Choosing color palettes and typography
- Reviewing code for UX issues
- Building landing pages or dashboards
- Implementing accessibility requirements

## What this skill adds

Baseline accessibility and UX heuristics — contrast ratios, touch-target sizes, line-height, motion timing — are assumed knowledge, not repeated here. What a model cannot know is the catalog: 11 searchable CSVs (styles, palettes, font pairings, chart and icon conventions, landing patterns) queried through `scripts/search.py`. That is the reason to invoke this skill; the rest of this file is how to query it.

## Prerequisites

Python 3 (`python3 --version`; on Windows, `python --version`). No third-party packages required.

---

## How to Use This Skill

When user requests UI/UX work (design, build, create, implement, review, fix, improve), follow this workflow:

### Step 1: Analyze User Requirements

Extract key information from user request:
- **Product type**: SaaS, e-commerce, portfolio, dashboard, landing page, etc.
- **Style keywords**: minimal, playful, professional, elegant, dark mode, etc.
- **Industry**: healthcare, fintech, gaming, education, etc.
- **Stack**: React, Vue, Next.js, or default to `html-tailwind`

### Step 2: Generate Design System (REQUIRED)

**Always start with `--design-system`** to get comprehensive recommendations with reasoning:

```bash
python3 skills/ui-ux-pro-max/scripts/search.py "<product_type> <industry> <keywords>" --design-system [-p "Project Name"]
```

This command:
1. Searches 5 domains in parallel (product, style, color, landing, typography)
2. Applies reasoning rules from `ui-reasoning.csv` to select best matches
3. Returns complete design system: pattern, style, colors, typography, effects
4. Includes anti-patterns to avoid

**Example:**
```bash
python3 skills/ui-ux-pro-max/scripts/search.py "beauty spa wellness service" --design-system -p "Serenity Spa"
```

### Step 2b: Persist Design System (optional)

To save the design system for hierarchical retrieval across sessions, add `--persist` (and `--page "<name>"` for a page override). The Master + Overrides pattern, the files it creates and the retrieval prompt are in `SEARCH.md`.

### Step 3: Supplement with Detailed Searches (as needed)

After getting the design system, use domain searches to get additional details:

```bash
python3 skills/ui-ux-pro-max/scripts/search.py "<keyword>" --domain <domain> [-n <max_results>]
```

**When to use detailed searches:**

| Need | Domain | Example |
|------|--------|---------|
| More style options | `style` | `--domain style "glassmorphism dark"` |
| Chart recommendations | `chart` | `--domain chart "real-time dashboard"` |
| UX best practices | `ux` | `--domain ux "animation accessibility"` |
| Alternative fonts | `typography` | `--domain typography "elegant luxury"` |
| Landing structure | `landing` | `--domain landing "hero social-proof"` |

### Step 4: Stack Guidelines (Default: html-tailwind)

Get implementation-specific best practices. If user doesn't specify a stack, **default to `html-tailwind`**.

```bash
python3 skills/ui-ux-pro-max/scripts/search.py "<keyword>" --stack html-tailwind
```

Available stacks: `html-tailwind`, `react`, `nextjs`, `vue`, `svelte`, `swiftui`, `react-native`, `flutter`, `shadcn`, `jetpack-compose`

---

## Before Delivery

Before delivering UI code, verify every item in the Pre-Delivery Checklist in `RULES.md` (visual quality, interaction, light/dark contrast, layout, accessibility). Common rules for professional UI are in the same file.

---

**Project-specific overrides:** if `SKILL.local.md` exists in this directory, read it — it is consumer-owned, survives framework refresh, and **wins on conflict**. A sidecar that relaxes a gate defined above must state how to prove the gate is wrong in that case. Doctrine: `rules/framework-vs-project-root.md`.
