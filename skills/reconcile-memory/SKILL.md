---
name: reconcile-memory
description: Shrink bloated memory files back to what actually earns its place in context, without losing knowledge. Use whenever memory has grown expensive or disorganized — key-facts.md is huge, MEMORY.md has drifted from the files it indexes, SessionStart injects a wall of text, a session starts with a big chunk of context already spent, entries have landed in the wrong file, or the user asks to clean up / audit / trim / optimize project memory or auto-memory. Also use when `forge doctor` reports a memory-size warning, and before onboarding a project whose memory nobody has pruned in months.
---

# Reconcile memory

Memory files are paid for on every single session, forever, whether or not that session touches the subject. A fact that saves ten minutes once a month is worth a line; the same fact spread over four paragraphs is a standing tax. This skill finds the difference and fixes it.

**The failure it exists to stop is not "the file got big".** It is content that was never memory-shaped landing in a memory file and then being loaded whole at every startup — a repo-state snapshot, an architecture write-up, a postmortem narrative. Those are real knowledge and must survive; they just belong somewhere nothing injects. A 6 KB key-facts.md of one-line facts is healthy. A 6 KB narrative is not, at any size.

Equally: **an empty memory file is also a failure.** The project pays a different tax when a session re-derives a fact someone already learned. Reconciling is not a cutting exercise — you are deciding, entry by entry, where knowledge lives so it is there when it matters and absent when it doesn't. If you finish and the project is worse off next session, you have done the wrong thing.

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

### Two destinations, and why the obvious one is not always right

`MEMORY-SCHEMA.md` routes by kind — bugs to `bugs.md`, decisions to `decisions.md`, conventions to `patterns.md`. Those three are read on demand, so an entry moved there costs nothing at startup and stays findable.

**But the index is injected, and every entry in those three files earns a line in it.** `forge memory reindex` builds `index.md` from their entry headings, and `index.md` loads at every SessionStart alongside `key-facts.md`. So relocation is not free: it converts a large per-session cost into a small one, roughly 100 bytes of index per entry, not into zero.

That is fine for entries. It is the wrong move for bulk. Measured on a 63 KB key-facts.md: routing 21 blocks by kind shrank the injected total to 11 142 B, while lifting the same two sections out whole to non-indexed files reached 8 024 B — the index growth ate a fifth of the saving, and the second approach also kept the material verbatim instead of chopping it into entries it was never written as.

So choose by shape:

| What you are moving | Where it goes | Why |
|---|---|---|
| An individual fact, decision, bug or convention | `decisions.md` / `bugs.md` / `patterns.md` | Indexed, findable, ~100 B/session for the index line |
| A whole coherent section — an architecture baseline, a repo-state chronology, a design of record | `docs/project-memory/reference/<topic>.md`, moved **verbatim** | `memory_index.py` scans only the three entry files, so this is invisible to the index and costs literally nothing per session |

Leave exactly one line in `key-facts.md` pointing at a file you moved wholesale, so a reader still knows it exists. `docs/**` is excluded from the refresh rsync, so this destination is project data that survives a framework refresh untouched.

`.claude/reference/` (Tier 2) is a legitimate home for material that is genuinely "what the system IS" rather than a remembered fact, and populated `NN-*.md` files there survive refresh because the framework only ships the `NN-*.template.md` variants. But that is a documentation-governance decision with an ADR attached, so **propose it and let the user choose** — do not move anything there unprompted.

**Where this skill stops:** age-based cleanup within `bugs.md` / `decisions.md` / `patterns.md` belongs to `/remember archive`, which already does it. Reconcile decides *which file* an entry belongs in; archive decides *whether it is still current*. If you finish and the destination files are themselves stale, say so and suggest `/remember archive` — don't reimplement it.

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

This matters because the pull is entirely one way. Nothing about a reconcile rewards leaving things alone, so the temptation is to find *something* to cut and call it progress. Measured: on an already-healthy 8 KB store, a reconcile pass trimmed it to 70% of its original size while a plain reading of the same store trimmed it to 88% — the extra cutting bought nothing a session would notice and spent judgment on entries that were fine. A reconcile that reports "already healthy, three entries could be tightened, none of it worth your time" is a complete and successful run.

Act when you can name the defect: over the cap, narrative in an injected file, an index that disagrees with its files, entries falsified by the current code, or two entries covering one fact. Absent one of those, stop.

Restraint is about not inventing work, not about declining work you found. Two entries stating the same rule is a nameable defect — the next reader has to decide which is current, and both load every session. Merge them. Likewise, replacing a falsified entry with a dated stub still leaves something loading at every startup: keep a stub when the fact was real and its supersession is itself worth knowing, and delete outright when the entry was simply wrong, since a wrong memory asserted with confidence costs more than a missing one. Measured: a pass that stubbed four false entries and declined two obvious merges saved 43 bytes, against 1 437 bytes for the same store handled with merges — the diagnosis was better and the outcome was not.

### 3. Classify every entry

Read the whole file. For each entry decide keep / relocate / delete / merge, and be able to say why in a few words. Where an entry's fate depends on whether the code still works that way, check — a claim you cannot verify is a claim you should not silently keep. This is the part that needs judgment and cannot be scripted; a size threshold alone would evict good one-line facts from a long file and keep a short bad narrative.

### 4. Present the plan, then apply on approval

Memory is committed history and the auto-memory store is not versioned at all, so a bad eviction loses knowledge with nothing to recover it from. Show the plan first:

```
docs/project-memory/key-facts.md — 63 618 B, over the 20 000 cap (tail already dropped)

  KEEP      12 entries  (1 403 B)   one-line facts, current
  RELOCATE   8 entries  (26 846 B)  -> decisions.md — "Technical Baseline" is
                                       decisions of record, not facts
  DELETE     1 section  (34 746 B)  -> "Current Repository State", a 2026-07-07
                                       snapshot; 6 of its 9 claims no longer
                                       match the tree. Replaced by one dated
                                       superseded line.
  RESULT    ~4 KB, fully injected, nothing truncated
```

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

If that number did not move, nothing you did reached the thing you were fixing.

**One trap specific to rewriting `key-facts.md`:** the hook injects it only when some line starts with `- **`, a template artefact the schema never required (tracked as T919). Until that lands, keep at least one `- **Label:** value` line, or a perfectly valid file of plain bullets vanishes from SessionStart with no error — which is the exact silent loss this skill exists to prevent. The verification probe above catches it: a zero-length KEY FACTS block means you tripped the gate. Report *that* figure as the headline, not the change to `key-facts.md` alone — the hook output is the only number that includes the index growth your relocations caused, which is exactly the cost a per-file measurement hides.

## Reporting

Finished-work report per `skills/_shared/report-format.md`. The Result field carries the before/after byte counts and the hook-output measurement — a reconcile that cannot state how many bytes it removed has not demonstrated anything.

Flag two things explicitly when they apply: entries you deleted that someone might miss, and any store you left alone because it was already healthy. A reconcile that reports only what it cut reads like progress even when it did harm.

---

**Project-specific overrides:** if `SKILL.local.md` exists in this directory, read it — it is consumer-owned, survives framework refresh, and **wins on conflict**. A sidecar that relaxes a gate defined above must state how to prove the gate is wrong in that case. Doctrine: `rules/framework-vs-project-root.md`.
