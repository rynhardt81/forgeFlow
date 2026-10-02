---
name: reconcile-memory
description: Shrink bloated memory files back to what actually earns its place in context, without losing knowledge. Use whenever memory has grown expensive or disorganized — key-facts.md is huge, MEMORY.md has drifted from the files it indexes, SessionStart injects a wall of text, a session starts with a big chunk of context already spent, entries have landed in the wrong file, or the user asks to clean up / audit / trim / optimize project memory or auto-memory. Also use when `forge doctor` reports a memory-size warning, and before onboarding a project whose memory nobody has pruned in months.
---

# Reconcile memory

Memory files are paid for on every single session, forever, whether or not that session touches the subject. A fact that saves ten minutes once a month is worth a line; the same fact spread over four paragraphs is a standing tax. This skill finds the difference and fixes it.

Equally: **an empty memory file is also a failure.** The project pays a different tax when a session re-derives a fact someone already learned. Reconciling is not a cutting exercise — you are deciding, entry by entry, where knowledge lives so it is there when it matters and absent when it doesn't. If you finish and the project is worse off next session, you have done the wrong thing.

## Index

| File or section | Read when… |
|---|---|
| `DESTINATIONS.md` | Choosing where relocated content goes, and why |
| `PLAN-EXAMPLE.md` | The step-4 plan |
| `RATIONALE.md` | Why size is a tax; measured evidence against over-cutting |
| `_shared/report-format.md` | The finished-work report |

## The two stores, and the rule against mixing them

| Store | Path | Injected at SessionStart | Committed |
|---|---|---|---|
| **Project memory** | `docs/project-memory/` | `index.md` + `key-facts.md` only | Yes — team-shared |
| **Harness auto-memory** | `~/.claude/projects/<slug>/memory/` | `MEMORY.md` only | No — per-machine |

`<slug>` is derived from the project's absolute path, but the transform has edge cases — `/` becomes `-` *and* dots are dropped, so `/Users/x/.claude` becomes `-Users-x--claude`. Locate the directory rather than construct it:

```bash
ls -d ~/.claude/projects/*"$(basename "$PWD")" 2>/dev/null   # usually enough
ls ~/.claude/projects/                                        # otherwise, eyeball it
```

A project that has no directory there simply has no auto-memory yet — that is not a defect, and there is nothing to reconcile.

**Reconcile each store inside itself. Never move content between them.** They have different jobs and different audiences: project memory is the team's durable record, auto-memory is one machine's working context. Moving auto-memory into a repo also defeats whatever guards the boundary: a hook that inspects Write/Edit calls sees a file write, not a `git commit`, so a note naming a client or employer can land in committed history with nothing to catch it. If a fact genuinely belongs in the other store, say so in the plan and let the user re-capture it with `/remember`; do not relocate it yourself.

## What earns a place in an injected file

Apply this to `key-facts.md` and `MEMORY.md` — the two files that cost tokens at every startup.

**Shape is the test, not size.** `MEMORY-SCHEMA.md` already says key-facts entries are single lines. So:

- **Keep**: a one-line fact that is current, specific, and would cost real time to rediscover. Ports, account names, magic values, a non-obvious constraint, "this subsystem is inert".
- **Relocate**: anything multi-line, or over roughly 200 characters, or narrating *how* something came to be true. It is a decision, a pattern, or a bug story wearing a fact's clothes. Route it by kind and leave nothing behind — `index.md` is the pointer, and reindex regenerates it.
- **Delete**: anything falsified by the current code, or a snapshot of state that has since moved on. A repo-state listing from four months ago is not knowledge, it is a stale claim that will mislead a future session more than silence would. When the entry recorded something real that has simply been superseded, keep one dated line saying so rather than the whole body.
- **Merge**: near-duplicates. Two entries covering one fact means the next reader has to work out which is current.

### Where relocated content goes

Single entries go to `decisions.md` / `bugs.md` / `patterns.md` (~100 B/session of index each). A whole section goes **verbatim** to `docs/project-memory/reference/<topic>.md`, leaving one pointer line in `key-facts.md`. Age-based cleanup is `/remember archive`'s job. Details: `DESTINATIONS.md`.

Content that is "what the system IS" rather than a remembered fact — an architecture baseline, a technical design of record — is Tier 2 material and belongs in `.claude/reference/`. That move is a documentation decision with governance attached, so **propose it and let the user decide**; reconcile does not write to `reference/` on its own.

## Workflow

### 1. Measure before you touch anything

Report actual numbers, not impressions. The point is a before/after the user can check.

```bash
# Project memory
wc -c docs/project-memory/*.md
# Per-section breakdown of the injected file — where the weight actually is
awk '/^## /{h=$0} {n[h]+=length($0)+1} END{for(k in n) printf "%8d  %s\n", n[k], k}' \
    docs/project-memory/key-facts.md | sort -rn
# Harness auto-memory for this project
wc -c "$(ls -d ~/.claude/projects/*"$(basename "$PWD")" | head -1)"/memory/*.md 2>/dev/null | tail -20
```

The SessionStart hook caps `index.md` and `key-facts.md` at 20 000 characters each. **Over the cap means content is already being silently dropped mid-file** — those projects are urgent, because the tail is not reaching sessions at all and nobody has been told. Under the cap is not automatically fine; a 15 KB file of narrative still costs every session.

### 2. Decide whether to act at all

Before classifying anything, ask whether this store has a problem. A store of one-line dated facts, under the cap, with an index that matches its files, is finished — and the correct output is to say so and stop.

Act when you can name the defect: over the cap, narrative in an injected file, an index that disagrees with its files, entries falsified by the current code, or two entries covering one fact. Absent one of those, stop.

Restraint is about not inventing work, not about declining work you found. Two entries stating the same rule is a nameable defect — the next reader has to decide which is current, and both load every session. Merge them. Likewise, replacing a falsified entry with a dated stub still leaves something loading at every startup: keep a stub when the fact was real and its supersession is itself worth knowing, and delete outright when the entry was simply wrong, since a wrong memory asserted with confidence costs more than a missing one.

### 3. Classify every entry

Read the whole file. For each entry decide keep / relocate / delete / merge, and be able to say why in a few words. Where an entry's fate depends on whether the code still works that way, check — a claim you cannot verify is a claim you should not silently keep. This is the part that needs judgment and cannot be scripted; a size threshold alone would evict good one-line facts from a long file and keep a short bad narrative.

### 4. Present the plan, then apply on approval

Memory is committed history and the auto-memory store is not versioned at all, so a bad eviction loses knowledge with nothing to recover it from. Show the plan first:

Shape: `PLAN-EXAMPLE.md` (per file: size vs cap, KEEP / RELOCATE / DELETE with counts, bytes and reason, RESULT).

Name what you checked for the delete line — "6 of its 9 claims no longer match the tree" is a finding; "looked stale" is a guess. On approval, apply the whole plan through to reindex without stopping for further confirmation.

### 5. Apply

Relocate first, delete second, so nothing is dropped before its replacement exists. Then:

```bash
python3 .claude/scripts/forge/forge.py memory reindex
```

Reindex regenerates `index.md` from the entry headings — deterministic and idempotent. Never hand-edit the index; an entry missing from it is invisible to future sessions, which is exactly the knowledge loss this skill is supposed to prevent.

For the harness store, `MEMORY.md` is the index and is hand-maintained: one line per memory file, `- [Title](file.md) — hook`. Reconciling it means deleting lines whose files are gone, adding files that have no line, merging duplicates, and shortening hooks that have grown into summaries. Delete a memory file outright when it records something now false — a wrong memory is worse than a missing one, because it is asserted with confidence.

### 6. Verify with the same probe you started with

Re-run the measurement from step 1 and show before/after. Then confirm the injected result is what you think it is by running the hook itself rather than reasoning about it:

```bash
echo '{}' | python3 .claude/hooks/session/session-context.py | wc -c
```

If that number did not move, nothing you did reached the thing you were fixing. Report *that* figure as the headline, not the change to `key-facts.md` alone — the hook output is the only number that includes the index growth your relocations caused, which is exactly the cost a per-file measurement hides.

## Reporting

Finished-work report per `skills/_shared/report-format.md`. The Result field carries the before/after byte counts and the hook-output measurement — a reconcile that cannot state how many bytes it removed has not demonstrated anything.

Flag two things explicitly when they apply: entries you deleted that someone might miss, and any store you left alone because it was already healthy. A reconcile that reports only what it cut reads like progress even when it did harm.

---

**Project-specific overrides:** if `SKILL.local.md` exists in this directory, read it — it is consumer-owned, survives framework refresh, and **wins on conflict**. A sidecar that relaxes a gate defined above must state how to prove the gate is wrong in that case. Doctrine: `rules/framework-vs-project-root.md`.
