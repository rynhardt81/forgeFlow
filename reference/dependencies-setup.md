# Dependency hygiene — per-ecosystem setup

> Not auto-loaded. Moved verbatim from `rules/dependencies.md` on 2026-10-22; that rule keeps the four principles every session needs. Read this when configuring a package manager or CI.

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
