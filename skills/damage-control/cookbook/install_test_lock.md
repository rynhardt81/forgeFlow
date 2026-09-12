# Install the Test Lock

Closes the "make the test green by editing the test" escape during `/fix-bug`.

## What it does

`/fix-bug` writes a regression test that fails, commits it, then fixes the source
until it passes. The failure mode is editing the *test* instead of the source: the
suite goes green, the bug ships, and `fix_bug_regression.py` only notices at Stop,
once the work is already done.

This hook denies writes to any path listed in `.claude/.test-lock` while a fix is in
progress. It is **opt-in by design** — framework hooks are advisory and never block,
so blocking behaviour lives here and a project installs it deliberately.

## Prerequisites

`python3` on PATH. No dependencies — unlike the other damage-control hooks, this one
needs no `uv` and no `pyyaml`.

## Install

### Step 1 — choose the scope

Use `AskUserQuestion`:

```
Question: "Where should the test lock apply?"
Options:
  - "Project (Recommended)" — .claude/settings.json, shared with the team
  - "Project Personal"      — .claude/settings.local.json, just you, gitignored
```

Global installation is deliberately not offered: the lock is meaningful only in a
repository that runs `/fix-bug` with committed regression tests.

### Step 2 — copy the hook

```bash
mkdir -p .claude/hooks/damage-control
cp .claude/skills/damage-control/hooks/damage-control-python/test-lock-damage-control.py \
   .claude/hooks/damage-control/
chmod +x .claude/hooks/damage-control/test-lock-damage-control.py
```

### Step 3 — wire it

Merge into the chosen settings file. `PreToolUse`, matching the write tools:

```json
{
  "hooks": {
    "PreToolUse": [
      {
        "matcher": "Edit|Write|MultiEdit|NotebookEdit",
        "hooks": [
          {
            "type": "command",
            "command": "python3 \"$CLAUDE_PROJECT_DIR/.claude/hooks/damage-control/test-lock-damage-control.py\"",
            "timeout": 5
          }
        ]
      }
    ]
  }
}
```

### Step 4 — ignore the lock file

```bash
echo ".claude/.test-lock" >> .gitignore
```

The lock is per-developer working state, not a project artifact. Committing it would
block your teammates on a fix they are not doing.

### Step 5 — prove it works, in both directions

A blocking hook you have not falsified is a blocking hook you do not have.

```bash
printf 'tests/test_example.py\n' > .claude/.test-lock
```

Ask Claude to edit `tests/test_example.py` — it must be refused, and the message must
name the file and how to clear the lock. Then ask it to edit a source file — that must
succeed. Then:

```bash
rm .claude/.test-lock
```

and confirm the test file is editable again. **The last step is the one people skip**,
and a lock left behind blocks the next session's legitimate test edits with no obvious
cause.

## Usage

`/fix-bug` step 4 writes the committed test's path into the lock; step 5 clears it. To
drive it by hand:

```bash
echo "tests/test_login_regression.py" >> .claude/.test-lock   # start the fix
rm .claude/.test-lock                                          # fix verified
```

One path per line, relative to the project root. Blank lines and `#` comments are
ignored. **No lock file, or an empty one, blocks nothing** — that is the normal state.

## When the test really is wrong

Sometimes the regression test encodes the wrong expectation. That is a legitimate
reason to edit it, and the hook is not trying to stop you — it is trying to stop the
edit happening *silently* as the path of least resistance. Say why the test is wrong,
`rm .claude/.test-lock`, and change it deliberately.

## Uninstall

Remove the `PreToolUse` entry from settings, delete
`.claude/hooks/damage-control/test-lock-damage-control.py`, and delete any
`.claude/.test-lock`.
