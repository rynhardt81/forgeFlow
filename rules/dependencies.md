# Dependency Hygiene Rules

> **Loaded at every session start** — all of `.claude/rules/*.md` is. Binding. Keep it short: opt-in depth belongs in a skill or `reference/`. See CONTRIBUTING.md "The rules budget".
>
> Applies to every project that consumes Forge Flow.

Supply-chain attacks via package managers (npm Axios, Tanstack; PyPI LiteLLM,
Mistral AI) and AI-agent "slop-squatting" (hallucinated near-name packages) have
moved this from theoretical to routine. Every `pip install` / `npm install` /
`uv add` executes arbitrary code from a stranger on the machine. These four
practices apply regardless of language.

## The four principles

### 1. Pin exact versions, not ranges

No unbounded ranges in any dependency spec. Tomorrow's compromised release must
not auto-install on the next sync.

### 2. Enforce a publish cool-down window

Refuse package versions published in the last 7 days (tighten to 14 for projects
holding real secrets; relax to 3 only on throwaway experiments). Most
compromised releases are detected and yanked within 24–48 hours.

### 3. Lockfile-strict in CI

The lockfile is ground truth. CI must fail if `pyproject.toml` / `package.json`
/ `Cargo.toml` and the lockfile have diverged. Default sync commands that
"reconcile" silently are the attack vector — an agent edits the manifest and
the lockfile follows. Strict mode is the fix.

### 4. Every dependency earns its place

The highest-leverage practice and the one that survives ecosystem churn.

**Agents must not add new dependencies without asking first.** Every dependency
needs an explicit justification: what it does, why stdlib won't work, install
surface size. For small functionality (~50 lines), prefer rewriting inline over
importing thousands of lines of transitive deps.

This is the only practice that defends against hallucinated package names a
setting cannot patch — the install simply does not happen.

---

## Implementation — Python (uv)

uv is the standard package manager. **Requires uv >= 0.10** — `add-bounds`
stabilized in 0.10.0. Check with `uv --version`; upgrade via `brew upgrade uv`
or your installer's equivalent. Verified end-to-end on uv 0.11.16
(`add-bounds = "exact"` fires, `uv sync --locked` returns rc=1 on lockfile
drift).

Drop this into `pyproject.toml`:

```toml
[tool.uv]
add-bounds = "exact"
exclude-newer = "7 days"
```

- `add-bounds = "exact"` → `uv add pkg` writes `pkg = "==1.2.3"`. Allowed
  values: `"lower"` (default), `"major"`, `"minor"`, `"exact"`.
- `exclude-newer = "7 days"` → resolver refuses any version published in the
  last 7 days. Accepts friendly durations (`"7 days"`), ISO 8601 (`"P7D"`), or
  RFC 3339 timestamps.

CI gate — must fail if lockfile diverges:

```bash
uv sync --locked
```

`--locked` asserts the lockfile will not change. Errors loudly on drift. Use
this in every CI pipeline and locally when pulling a branch an agent or
teammate touched.

A drop-in starter is at `templates/pyproject.toml.template` — copy, fill the
project metadata, commit `pyproject.toml` *and* `uv.lock` together.

## Implementation — bun

| Principle | Mechanism |
|---|---|
| Exact pins | `exact = true` under `[install]` in `bunfig.toml` (or `bun add --exact`) |
| Cool-down window | `minimumReleaseAge = 604800` (7 days, seconds) under `[install]` in `bunfig.toml` — native support |
| Lockfile-strict | `bun install --frozen-lockfile` in CI |
| CVE surveillance | `bun audit` — wire the scheduled scan via `templates/dependency-scan.yml` |
| Earn its place | Apply the agent rule in `CLAUDE.md` / `AGENTS.md` |

## Implementation — npm

| Principle | Mechanism |
|---|---|
| Exact pins | `npm config set save-exact true` (or `save-exact=true` in `.npmrc`) |
| Cool-down window | No native equivalent — use Renovate `minimumReleaseAge` (`templates/renovate.json`) or Socket.dev in CI |
| Lockfile-strict | `npm ci` in CI |
| CVE surveillance | `npm audit --audit-level=high` + `templates/dependency-scan.yml` |
| Earn its place | Apply the agent rule in `CLAUDE.md` / `AGENTS.md` |

## Implementation — cargo

| Principle | Mechanism |
|---|---|
| Exact pins | `=1.2.3` in `Cargo.toml` (cargo defaults to caret-equivalent) |
| Cool-down window | No native equivalent |
| Lockfile-strict | `cargo build --locked` |
| Earn its place | Apply the agent rule in `CLAUDE.md` / `AGENTS.md` |

## Implementation — other ecosystems

Apply the four principles. File a follow-up to populate this section when a
project introduces a new ecosystem.

---

## Agent instruction (drop into every project's CLAUDE.md)

```markdown
## Dependencies

- Never add a new dependency without asking first.
- Every dependency must earn its place — explain what it does, why a stdlib
  approach won't work, and how big the install surface is.
- For small functionality (one helper, a regex, ~50 lines), prefer rewriting
  inline rather than importing thousands of lines of transitive dependencies.
- When a library is the right call, prefer one with few transitive deps,
  active maintenance, and a clear publish history.
```

## Project-specific extensions

`rules/dependencies.local.md` — survives refresh, wins on conflict.

## See also

- `rules/security.md` — broader security gating
- `templates/pyproject.toml.template` — drop-in uv starter with safe defaults
- `.claude/reference/03-security-auth-and-access.md` — per-project secrets handling
