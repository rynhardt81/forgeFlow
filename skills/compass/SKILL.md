---
name: compass
description: "Plan a huge chunk of work (more than one agent session can hold) as a shared map of decision tickets on the forge registry, and resolve them one at a time until the way to the destination is clear. Use when an idea is too big and too foggy for one session or one /grilling pass. NOT FOR work whose route is already clear (use /intent or /new-feature)."
disable-model-invocation: true
---

# Compass

## Index

| File or section | Read when… |
|---|---|
| `MAP.md` | Charting — the map body template, fog of war, out of scope |
| Plan, don't do · Refer by name · The map · Ticket types (below) | Every invocation |
| Chart the map / Work through the map (below) | The mode you were invoked in |
| `_shared/model-routing.md` | Dispatching a research subagent |

A loose idea has arrived, too big for one agent session, and wrapped in fog: the way from here to the **destination** isn't visible yet. Finding that way is the job, not charging at the destination. This skill charts the way as a **shared map** on the forge registry, then works its **decision tickets** (questions whose resolution is a decision, not slices of a build to execute) one at a time until the route is clear.

The destination varies per effort, and naming it is the first act of charting: it shapes every ticket. It might be a spec to hand off, a decision to lock before planning starts, or a change made in place like a data-structure migration.

## Plan, don't do

Compass is **planning** by default: each ticket resolves a decision, and the map is done when the way is clear, with nothing left to decide before someone goes and does the thing. The pull to just do the work is usually the signal you've reached the edge of the map and it's time to hand off — to `/intent` (a spec someone must accept) or to build tasks in an ordinary epic (`/run-epic`). An effort can override this in its **Notes**, carrying execution into the map itself, but absent that, produce decisions, not deliverables.

## Refer by name

In everything the human reads (narration, the map's Decisions so far), refer to a ticket by its **name** — its task name, phrased as the question — never by a bare id. A wall of `T412, T413, T414` is illegible; names read at a glance. The id rides inside, never stands in: `**Which queue backs retries?** (T413)`.

## The map

The map is **one epic**, named `Compass: <destination>`; its body file holds the map (template: MAP.md). Its tickets are tasks in that epic. The map is an **index**, not a store: a decision lives in exactly one place, its ticket, so the map never restates it, only gists it and links.

| Compass concept | Forge operation |
|---|---|
| Create the map | `forge epic add E## --name "Compass: <destination>"`, then write the body sections into its body file |
| A ticket | `forge task add T### --epic E## --name "<the question>" --category decision:<type>`; body `## Question` |
| Blocking | `forge task set-deps T### --deps T###,…` — a ticket is unblocked when every ticket blocking it is completed |
| The **frontier** | `forge task ls --epic E## --ready` — open, unblocked, unclaimed (a locked ticket is not ready) |
| **Claim** | `forge task lock T### --session <id>` **first**, before any work, so concurrent sessions skip it |
| Resolve | append `## Resolution` to the ticket body, `forge task complete T###`, add a line to Decisions so far |

`decision:` tickets are decisions, not implementation work: `/run-epic` skips them, and they never carry build scope.

## Ticket types

Every ticket is **HITL** (worked *with* a human who speaks for themselves) or **AFK** (agent alone). A HITL ticket only resolves through that live exchange; the agent never stands in for the human's side of it (a grilling agent that answers its own questions has broken this).

- **`decision:research`** (AFK): reading documentation, third-party APIs or local knowledge to surface a fact a decision waits on. Resolved by a subagent routed per `_shared/model-routing.md` (E2 → `worker-e2`), writing its findings to `docs/processed/research/<slug>.md` (Tier 3 evidence) with a context pointer from the ticket.
- **`decision:prototype`** (HITL): raise the fidelity of the discussion with a cheap, rough, concrete artifact to react to, via `/prototype`. Link it from the ticket. Use when "how should it look" or "how should it behave" is the key question.
- **`decision:grilling`** (HITL): conversation. The default case. Run `/grilling` and `/domain-modeling`.
- **`decision:task`** (HITL or AFK): manual work that must happen before a decision can be made — signing up for a service so its API can be judged, provisioning access, moving data so its shape can be seen. The one type that *does* rather than decides, and it earns its place by unblocking a decision. The agent drives it alone where it can; otherwise it hands the human a precise checklist (`/wizard`). Its resolution records what was done and any resulting facts (credentials location, URLs, row counts) later tickets depend on.

## Invocation

Two modes. Either way, **never resolve more than one ticket per session**, research tickets excepted.

### Chart the map — `/compass "<loose idea>"`

1. **Name the destination.** Run `/grilling` and `/domain-modeling` to pin down what this map is finding its way to: the spec, decision, or change. The destination fixes the scope, so it's settled first.
2. **Map the frontier.** Grill again, **breadth-first**: fan out across the whole space rather than deep on any one thread, surfacing the open decisions and the first steps takeable now. **If this surfaces no fog** (the way is already clear, the journey small enough for one session), you don't need a map: stop and ask how the user would like to proceed.
3. **Create the map** (MAP.md): Destination and Notes filled in, Decisions so far empty, the fog sketched into **Not yet specified**.
4. **Create the tickets you can specify now**, then wire blocking in a **second pass** with `set-deps`. Everything you can't yet specify stays in the fog.
5. **Fire the research subagents** for each `decision:research` ticket, in parallel and in the background.
6. Stop: charting is one session's work; it hand-resolves nothing.

### Work through the map — `/compass E## [T###]`

1. Load the **map** — the epic body, not every ticket body.
2. Choose the ticket: the one named, else the first frontier ticket. **Claim it** before any work.
3. Resolve it as the type its category names — read the category, not just the body. Zoom as needed: read any related or completed ticket on demand; run the skills the map's **Notes** name. If in doubt, `/grilling` and `/domain-modeling`.
4. Record the resolution: `## Resolution` in the ticket body (assets linked, not pasted), `forge task complete`, and one line in Decisions so far.
5. Add newly surfaced tickets (create, then wire); graduate any fog the answer has made specifiable, clearing it from **Not yet specified**. A ticket the answer shows to sit beyond the destination is **ruled out of scope** (MAP.md), not resolved on the route. If the decision invalidates other parts of the map, update those tickets.

The user may run frontier tickets in parallel sessions: expect the registry to change underneath you, and re-read the frontier before claiming.

<!-- Adapted from mattpocock/skills wayfinder (MIT) — see THIRD-PARTY-NOTICES.md. Issue-tracker operations replaced by forge registry ones. -->

---

**Project-specific overrides:** if `SKILL.local.md` exists in this directory, read it — it is consumer-owned, survives framework refresh, and **wins on conflict**. A sidecar that relaxes a gate defined above must state how to prove the gate is wrong in that case. Doctrine: `rules/framework-vs-project-root.md`.
