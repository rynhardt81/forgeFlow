# Hook Rules

> Active directive. Discovered on-demand via the `rules/*.md` glob — read by `/audit-rules` and any agent reasoning about hooks. Hooks are Python scripts that fire on Claude Code lifecycle events. **Advisory only** — never block, surface info or auto-fix trivial drift. **No hook may spawn an LLM subprocess** — hooks are deterministic scripts, full stop.

## Events wired in `hooks/settings.json`

| Event | Matcher | Hook | Purpose |
|-------|---------|------|---------|
| `SessionStart` | startup, resume, compact | `session/session-context.py` | Inject project memory (`docs/project-memory/index.md` + `key-facts.md`) and auto-create the session file |
| `SessionStart` | startup, resume, compact | `forge/consistency-banner.py --fix --summary` | Auto-fix registry/task-file drift; banner if unfixable |
| `UserPromptSubmit` | (any) | `context/user-prompt-submit.py` | Inject active session/skill/agent context into the prompt |
| `PreToolUse` | `Bash` | `validation/pr-skill-reminder.py` | Nudge toward `/create-pr` when a raw `gh pr create` is attempted |
| `PreToolUse` | `Write` &#124; `Edit` | `validation/validate-edit.py` | Warn on edits to `.env`, lockfiles, `.git/`, `node_modules/` |
| `PostToolUse` | `Write` &#124; `Edit` | `forge/consistency-banner.py --fix --json` | Re-check consistency on every write |
| `PostToolUse` | `Write` &#124; `Edit` | `forge/isa-reflection-emit.py` | Append a reflection skeleton to `daily/algorithm-reflections.jsonl` when an ISA reaches `phase: complete` |
| `PostToolUse` | (any) | `forge/checkpoint-nudge.py` | Remind background worktree agents to checkpoint-commit |
| `SessionEnd` | (any) | `session/session-end-cleanup.py` | Archive session files atomically |

Validator hooks bind per-agent and per-skill via `hooks:` frontmatter in `agents/*.md` and `skills/*/SKILL.md`. On `PostToolUse` events their advice is emitted as `hookSpecificOutput.additionalContext` so the model actually receives it.

## consistency-banner — the trust boundary

`forge/consistency-banner.py` makes the forge CLI's atomicity guarantees real at the framework level:

1. Reads `docs/tasks/registry.json` and the matching task files
2. Detects drift between registry status and file frontmatter status
3. With `--fix`: auto-corrects trivial drift
4. With `--summary` or `--json`: reports remaining drift requiring human judgment

If the banner shows blocking drift, fix it before continuing.

## What was deliberately removed (v4)

- Automatic transcript capture (`memory-capture.py`) and the flush/compile pipeline — knowledge capture is manual and intentional via `/remember`.
- The CLAUDE.md rule-reflection hook — hooks must never spawn `claude` subprocesses; rule reflection is `/audit-rules`, run by a human.
- `security-check.py` and the `security/` allowlist pipeline — it warned into a channel nothing read. Blocking command security is the `/damage-control` skill's hooks, which actually block.

## See also

- `.claude/hooks/README.md` — hook authoring guidance, token economy, disable/configure procedures
- `.claude/agents/README.md` — agent roster and validator bindings
