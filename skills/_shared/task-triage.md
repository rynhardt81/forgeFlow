# Shared Task-Triage Rule

> Single source of truth for **what happens when work discovers more work**. Binding on every site that files a derived task — `/fix-bug`, `/create-pr` deferrals, `/security-review`, `/triage-incident`, `/run-epic` mid-epic discoveries, and ALGORITHM's phased hardening. Update this file; consumers inherit.

## The problem this exists to prevent

Executing a task surfaces bugs, review findings, and hardening gaps. Filed straight into the queue, they are indistinguishable from planned work — so next-task selection happens by feel, which biases toward "fix what I just broke." Reactive work crowds out the roadmap, and it self-feeds: every fix is itself reviewed, which files more findings. Weeks pass; nothing shipped but bug fixes.

## The question

Before filing anything, answer one question — **"what breaks if this ships later?"** — with exactly one of three answers.

### Blocker — the work in hand is *wrong* without it

Then it is **not a new task**. Two correct moves:

- Fold it into the current task. A guard the current change needs is part of the current change.
- Express it as a real dependency: `forge task add T### --deps <the task it blocks>`. Ordering constraints already have a mechanism; a new queue entry is not one.

Filing a blocker as a free-floating task is how a hard ordering constraint becomes a thing you have to remember.

### Next — must happen, but the current work is still correct and shippable

Normal queue, active epic:

```bash
forge task add T### --epic <active-epic> --name "..."
```

The test: could you ship the current work today, with this outstanding, and not be wrong? If yes and it still genuinely must happen, it is Next.

### Deferred — hardening, polish, robustness, "should also handle"

The backlog epic:

```bash
forge task add T### --epic E99 --name "..."
```

**This is the default.** When you are unsure between Next and Deferred, it is Deferred — the deferred pile is visible in every `task ls --ready` footer and promotable in one command, so being wrong costs a promotion, not a lost finding.

## The one carve-out: hard floors are never deferred by default

Schema, auth, money paths, and security findings are **blocker-or-next**, never Deferred by the default answer. (CLAUDE.md operational rules — hard floors never scale down.) This is the mechanical form of "unless it is a requirement to fix it right now."

Deferring a hard-floor finding is a deliberate, stated exception, not a default. `/audit-task-status` flags any deferred task carrying a security severity code as a **triage-rule violation**.

## The backlog epic

**One per project: `E99-hardening`.** Create it once:

```bash
forge epic add E99 --name "Hardening" --status backlog
```

Tasks in a `backlog` epic are excluded from `task ls --ready`, from `/run-epic`'s next-task selection, and from every other queue view. They are not lost: every `task ls --ready` prints how many are parked and how old the oldest is, and completing an epic reports the same and names the promote command.

Promote a whole batch when you decide it is hardening time:

```bash
forge epic status E99 in_progress
```

**Split the bucket only when one bucket actually hurts** — when an all-at-once promotion is too large to swallow. Domain buckets (`E98-security-backlog`, `E97-perf-backlog`) are legal, and `forge task move T### --epic E98` moves already-filed tasks into them. Do not guess at the split up front.

## Worked examples

| Discovery | Answer | Why |
|-----------|--------|-----|
| The function you are editing crashes on empty input, and your change calls it with empty input | **Blocker** | Fold in. Your change is wrong without it. |
| The same function crashes on empty input, but nothing reaches it that way yet | **Deferred** | Real, not urgent. `--epic E99`. |
| Review finds the new endpoint has no auth check | **Blocker / Next** | Hard floor. Never deferred. |
| Review finds the new endpoint has no rate limit | **Next or Deferred** | Ship-blocking only if abuse is live. Otherwise E99. |
| A migration you just wrote drops a column that another service reads | **Blocker** | Hard floor (schema). Fold in or revert. |
| Tests pass but coverage on the new branch is thin | **Deferred** | E99. |
| A prereq is missing and the current task cannot proceed | **Blocker → `--deps`** | An ordering constraint, not a queue entry. |
| An incident postmortem's "what prevents the class" item | **Deferred** | E99, unless the class is live and recurring. |

## Anti-patterns

- **Filing everything as Next "to be safe."** That rebuilds the flat pile this rule exists to prevent. Deferred is the default; the footer keeps it honest.
- **Deferring a hard floor because the queue looks busy.** The carve-out has no exception clause.
- **Filing a blocker as a task instead of a dep.** A dependency that lives only in your head is a dependency nobody can see.
- **Creating a new backlog epic per finding.** One bucket until one bucket hurts.
