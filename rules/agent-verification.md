# Agent-Output & Fix-Completeness Rules

> Active directive. Discovered on-demand via the `rules/*.md` glob — read by `/audit-rules` and binding whenever you dispatch a subagent or declare a fix done. A delegated conclusion and a green focus-test are inputs to verification, never substitutes for it.

## Why this exists

Delegation and a passing test both feel like done. Neither is. A subagent returns a confident verdict from a partial view; a focus-test proves the line you changed, not the callers that share its path. Accepting either at face value is how a lax loop ships a confident wrong fix. This rule makes the cheap trap expensive: verify the claim, trace the blast radius, then declare.

## Verify agent output — don't relay a verdict you didn't check

When you dispatch a subagent (Agent tool, `/run-epic --parallel`, any delegated task):

- **The agent's final message is a claim, not a fact.** Before you act on it or relay it to the user, confirm it against ground truth you can see — the file, the test output, the actual command result. "The agent said it's fixed" is not evidence it's fixed.
- **Check the blast radius the agent actually touched**, not the radius it reported. Read the diff / files it changed. An agent scoped to one task routinely edits siblings, leaves a half-applied change, or reports success on a path it never exercised.
- **A NO-ACTION / "nothing to do" / "already correct" verdict gets MORE scrutiny, not less** — it's the one that lets you skip work, so it's the one most likely to be wrong in a way that costs you later. Before accepting "no change needed," check the real cost of it being wrong and confirm the thing it claims is already-correct actually is. Cheap-to-accept verdicts are where laxness hides.
- Independent agents disagreeing, or an agent's claim conflicting with what you already saw, is a signal to dig — not to pick the convenient one.

## A fix isn't done until you've traced every caller of the path

A bug report names a symptom on one path. The fix is done when every sibling that routes through the same code is covered — the fix at the shared choke point, or a conscious decision (stated) that a sibling is out of scope.

Before declaring a fix complete:

- **Grep every caller** of the function/script/path you changed. Patching only the path the ticket named leaves every sibling caller still broken — the class bug survives under a different entry point.
- **Trace every script and test that touches the same path**, including ones the ticket didn't mention. Stale paths, second entry points, and duplicate implementations are exactly what a focus-only fix misses.
- **A passing local test on the change-in-focus is not completeness evidence.** It proves the change you were looking at. It says nothing about the callers you didn't run. Run the sibling paths, or the broader suite, before you claim done.
- Prefer the root-cause fix at the shared choke point over N copies of a guard at each caller — it's a smaller diff AND it can't leave a sibling behind.

## Caller-sweep finds the entry points. Sibling-sweep finds the class.

Grepping callers traces the path *into* the function you changed. It does not cover the functions *beside* it — the sibling methods on the same class or module that share the same invariant and were written with the same blind spot. A bug is rarely one method's private mistake; it's the author's mental model applied uniformly, so the same flaw sits in every sibling that touched the same assumption.

When you fix a method, before declaring done:

- **Enumerate its siblings** — the other methods on the same class / in the same module that operate on the same state or enforce the same invariant (e.g. you fixed `deactivate`, look at `activate`, `delete`, `get`, `update` — the whole CRUD family, not just the one reported).
- **Ask of each: does the bug I just fixed exist here too?** Self-deactivation guard missing on `deactivate` → is it missing on every state-transition method? A tombstone check missing on `get` → missing on `list`, `count`, `exists`? A clobber on one writer → present on every writer?
- **The report names one symptom; the class shares one cause.** Sibling misses are invisible to a caller-sweep — no caller of `deactivate` will ever exercise `delete`. Only walking the sibling set surfaces them.

Caller-sweep and sibling-sweep are orthogonal and both required: callers find who reaches the code, siblings find who shares the mistake.

## The check, restated

Ground-truth the claim → read the real diff → grep every caller → sweep every sibling → run the sibling paths → *then* declare. Skip any step and "done" is a guess wearing a verdict.
