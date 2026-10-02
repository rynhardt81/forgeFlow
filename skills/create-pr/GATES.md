# Create PR — Pre-push Gate Mechanics

Commands, rationale and details behind the review-bot config and the Step 3.7 / Step 3.8 gates. The gates themselves — what blocks and when — are stated in SKILL.md.

## Contents

- Review bot configuration
- Step 3.7: Specialist review — plugin presence check, agent selection, intent compliance, fan-out
- Step 3.8: Local review-bot gate — rationale, prompt-argument quirk, AGENTS.md, resolve-then-invoke, quoting, background execution, triage, round cap, what it does not change, feedback signal

---

## Review bot configuration

```bash
git config forge.reviewBot    # e.g. "cc @codex — please review."  (post-PR mention)
git config forge.localReview  # e.g. "codex review --base {base}"  (pre-push gate, Step 3.8)
```

The two are independent and complementary: `localReview` runs the reviewer on your machine before the branch is pushed, `reviewBot` mentions it on the PR afterwards. Setting both is the intended configuration — the local pass absorbs the fix rounds that would otherwise each trigger CI.

To enable on a repo with a Codex-style reviewer installed: `git config forge.reviewBot "cc @codex — please review."`

---

## Step 3.7: Specialist review

Catches review-class issues *before* the push instead of burning CI minutes on fix-and-retry. **CI remains the gate of record** — this is additive.

**Plugin presence check first:**

```bash
python3 -c "import json,sys,os; d=json.load(open(os.path.expanduser('~/.claude/plugins/installed_plugins.json'))); sys.exit(0 if any(k.split('@',1)[0]=='pr-review-toolkit' for k in d.get('plugins',{})) else 1)" 2>/dev/null
```

Matches the plugin by its name-portion regardless of `@marketplace` suffix — the `installed_plugins.json` (schema v2) key is `pr-review-toolkit@claude-plugins-official`, never the bare name, so a `grep '"pr-review-toolkit"'` would never match. Missing file / bad JSON → non-zero exit → treated as absent (safe default).

**Agent selection** (deterministic — walk once against the changed files, accumulate matches):

| Diff pattern | Specialist (`pr-review-toolkit:` prefix) |
|--------------|------------------------------------------|
| Any code file (always) | `code-reviewer` |
| Test files (`*test*`, `*spec*`, `tests/`, `__tests__/`) | `pr-test-analyzer` |
| New types (`interface`, `type`, `class`, dataclass/Pydantic in diff) | `type-design-analyzer` |
| Error handling (`try/except`, `try/catch`, `.catch(`, `raise`) | `silent-failure-hunter` |
| Comments/docstrings touched | `comment-analyzer` |
| Final pass after MUST-FIX cleared (on request) | `code-simplifier` |

**Intent compliance:** if the task body for this branch carries an `Intent: intent/<slug>.md` line, read the file and hand `code-reviewer` a third question alongside bugs and style: does the diff deliver the intent's **Proposed outcome** and respect its **Constraints**? A diff that is correct but does not do what was asked is `MUST-FIX`. No intent line → no compliance pass; do not invent one.

**Fan-out:** single message, multiple Task tool uses — one per matched agent. Each gets the diff + changed-file list and returns findings as `MUST-FIX` (bug, security, broken test, regression) / `NICE-TO-HAVE` (style, naming, small refactor) / `NO-ACTION`. Aggregate into a compact per-agent count table + MUST-FIX detail lines.

---

## Step 3.8: Local review-bot gate

Same idea as 3.7, aimed at the one reviewer that otherwise costs CI minutes to consult. The configured review bot only ever sees the code **after** the PR exists, so every finding it raises is paid for with a full Actions run: fix → push → the whole matrix re-runs → the bot re-scans → repeat. A PR that takes 19 review rounds burns 19 matrices. Running the same reviewer locally, before the branch is pushed, moves that loop off Actions entirely.

**Config (per repo, mirrors `forge.reviewBot`):**

```bash
git config forge.localReview 'codex review --base {base}'
```

`{base}` is substituted with the Step 2 target branch. The value is a full command, so any reviewer CLI works — nothing here is specific to one vendor.

**Do not append review instructions to the command.** In codex-cli 0.144.1 a base-branch diff and a prompt argument are mutually exclusive:

```
error: the argument '--base <BRANCH>' cannot be used with '[PROMPT]'
Usage: codex review --base <BRANCH> [PROMPT]
```

The usage line printed with that error advertises the exact combination it just refused, so anyone who hits this will reasonably conclude they got the syntax wrong and keep trying variants. They didn't. The two are exclusive, and the base-branch diff is the half worth keeping — a prompt-only review has no defined scope.

**Guidance belongs in `AGENTS.md`, not in the invocation.** Codex reads `AGENTS.md` from the repo root automatically, so review direction placed there applies with no prompt argument and no arg conflict. Three reasons this is the better home regardless of the constraint:

- It is versioned and reviewed with the code, rather than living in one developer's shell history or a `git config` value nobody else has.
- The same file steers the **cloud** review, which sees the assembled PR and is where the more expensive findings tend to come from. One file improves both passes.
- It survives a framework refresh — it is project data at the repo root, not framework code under `.claude/`.

Put what the reviewer should weight there: which documents are authoritative, what counts as MUST-FIX in this repo, and any area it should not spend attention on.

**Quote the branch — this string is executed.** `git check-ref-format` permits
`;`, `$(…)`, backticks, `&&` and `|` in a branch name, so `release/foo;id` is a
legal branch, and substituting it raw appends a second command to whatever the
reviewer was supposed to run. Verified: a branch named `release/foo;touch PWNED`
creates the file when substituted bare, and does not when quoted.

```
--base 'release/foo;touch PWNED'      # inert: one argument
--base release/foo;touch PWNED        # two commands
```

Most branch names need no quoting, which is exactly why this is easy to miss —
you cannot tell by looking at the usual case. Quote unconditionally.

Piping the config value straight into a shell interpreter is the wrong shape and will be blocked outright on any machine running a defensive hook — it is the same pattern as the notorious download-and-execute one-liner, and the text being piped comes from config. `eval` is no better. Resolving first also means the exact command is visible in the transcript before it executes, which is what you want from something whose contents come out of config rather than out of this file.

**Run it in the background.** A review over a real diff takes long enough that a blocking call is a frozen turn of unknown length. Launch it detached (`run_in_background`) and let the harness re-invoke you when it exits — do **not** sit in a polling loop, which burns turns to learn nothing the completion notification would have told you.

The point of running it detached is that it overlaps **Step 3.7**: the specialist fan-out and this review read the same diff and do not depend on each other, so both proceed at once and the gate waits for the pair. That is the whole of the concurrency.

**Do not edit files while a review is in flight.** The reviewer reads the working tree. Editing underneath it means it reviews a mix of old and new state and reports findings against code that no longer exists — a phantom MUST-FIX that costs more to disprove than the review saved. If a fix cannot wait, kill the review and re-run it after the edit.

Triage the output into the same three buckets as 3.7 and Step 6: **MUST-FIX** / **NICE-TO-HAVE** / **NO-ACTION**. The reviewer emits prose, not structured findings, so this is a judgement call on free text — when a finding's severity is genuinely ambiguous, treat it as MUST-FIX and let the fix or the explicit deferral be the record.

Background execution does **not** relax the push gate. Step 5 must never create the PR while a review is still running — that defeats the gate entirely and leaves you paying for the post-PR rounds this step exists to remove. The concurrency is with 3.7 only; everything after the gate waits.

**Round cap — read this before looping.** Stop after **3** local review rounds and hand back to the user with what is still outstanding. Do not run the reviewer in an unattended loop, and never wire it into a hook or a `/loop`. This is the same failure shape as any LLM CLI invoked in a loop: a subscription meant for interactive use, billed by a process that never gets tired. Three rounds catches the ordinary case; a fourth means the change needs a human read, not another review pass.

**What this does not change:** the `forge.reviewBot` mention still goes in the PR body (Step 5) and Step 6 still runs. The bot gets a second pass over the assembled PR with full context, which the local diff review does not have. The difference is that it should now come back `NO-ACTION` or close to it — one Actions run instead of nineteen.

**Feedback signal:** if Step 6 surfaces a MUST-FIX that this step could have caught on the same diff, say so in the status report. Either the local invocation needs different instructions, or that finding class genuinely needs full-PR context — both worth knowing, and neither is visible unless it is named.
