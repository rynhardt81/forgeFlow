# The map body

Read from SKILL.md. The whole map at low resolution, loaded once per session. Open tickets are **not** listed in it: they are the epic's ready tasks, found by query.

## Template

Write these sections into the map epic's body file (`docs/epics/E##-*/E##-*.md`), replacing its placeholder sections:

```markdown
## Destination

<what reaching the end of this map looks like: the spec, decision, or change this effort is finding its way to. One or two lines; every session orients to it before choosing a ticket.>

## Notes

<domain; skills every session should consult; standing preferences for this effort>

## Decisions so far

<!-- the index: one line per completed ticket, enough to judge relevance; the ticket holds the detail -->

- **<ticket name>** (T###): <one-line gist of the answer>

## Not yet specified

<!-- fog of war: in-scope questions you can't ticket yet; graduates as the frontier advances -->

## Out of scope

<!-- work ruled beyond the destination; never graduates -->
```

## Fog of war

The map is *deliberately* incomplete: don't chart what you can't yet see. Beyond the live tickets lies the **fog of war**: the dim view of decisions you can tell are coming but can't yet pin down, because they hang on questions still open. Resolving a ticket clears the fog ahead of it, graduating whatever's now specifiable into fresh tickets, until the way to the destination is clear and no tickets remain.

**Not yet specified** is where that dim view is written down: the suspected question, the area to revisit later. Everything there is in scope, just not sharp enough to ticket. Write as loosely or as fully as the view allows; it doubles as a signpost for collaborators reading where the effort is headed.

**Fog or ticket?** The test is whether you can state the question precisely now, *not* whether you can answer it now.

- **Ticket when** the question is already sharp, even if it's blocked and you can't act on it yet.
- **Not yet specified when** you can't yet phrase it that sharply. Don't pre-slice the fog into ticket-sized pieces: one patch may graduate into several tickets, or none, once the frontier reaches it.

Not yet specified excludes what's already decided, what's already a live ticket, and what's out of scope.

## Out of scope

Fog only ever gathers *toward* the destination. Work beyond it is **out of scope**: it isn't fog, and it doesn't belong in Not yet specified. Scope, not sharpness, lands it here. It never graduates — it returns only if the destination is redrawn, and then as a fresh map.

When an existing ticket turns out to sit past the destination, close it without resolving it: `forge task rename T### "[out of scope] <name>"`, then lock and complete it (the registry has no won't-do status), and leave one line in **Out of scope** — the gist plus why, naming the ticket. It stays out of Decisions so far, which records the route actually walked.
