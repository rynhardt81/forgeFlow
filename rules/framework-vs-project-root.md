# Framework root vs. project root — never confuse them

> Active directive. Discovered on-demand via the `rules/*.md` glob — read by `/audit-rules` and any agent reasoning about framework/project path resolution. Treat as binding when encountered.

When the framework is vendored into a consumer project, the working directory the user runs `claude` from is **the project root**, but the framework's own code lives one level down in **`.claude/`**. These are two different roots and they own different things.

| Concept | Owns | In vendored install | In framework dev repo (self-hosting) |
|---|---|---|---|
| **framework_root** | CODE — `skills/`, `agents/`, `hooks/`, `scripts/`, `reference/`, `rules/`, `templates/` | `<project>/.claude/` | the repo root (e.g. `~/.../forgeFlow/`) |
| **project_root** | DATA — `docs/tasks/`, `docs/epics/`, `docs/project-memory/`, `daily/`, `ISA.md`, `CLAUDE.md` (project-level), generated artifacts (`docs/code-map.json`, `docs/visualizations/`) | `<project>/` (one up from `.claude/`) | the repo root (coincides with framework_root) |

In a vendored install they DIFFER. In the framework's own dev repo they COINCIDE — which is exactly why bugs of this class slip past dev-repo testing.

## The bug class to avoid

A function that needs to find one root and is *implemented* by walking up the directory tree looking for a marker file. The marker chosen looks safe in the framework's own dev repo, then fails in vendored installs because something in `.claude/` matches it.

### Markers that have caused this exact bug

| Marker | Why it failed | Fix |
|---|---|---|
| `CLAUDE.md` | Every `.claude/` directory has its own `CLAUDE.md` (the framework copy). The walk-up stopped one level too soon. | Drop this marker entirely. Use `.git` only. |
| `docs/code-map.json` | `install.sh` rsync used to copy the framework dev repo's own `docs/code-map.json` into `<project>/.claude/docs/`. The walk-up stopped in `.claude/` instead of the project. | Drop this marker. It's a derived artifact, not a structural one. |
| Any derived/gitignored file under `docs/` | Same shape — anything that can exist in the framework dev repo and *also* leak into `.claude/` via rsync becomes a false-positive trap. | Only use markers that are structural (`.git`) or project-distinguishing (`pyproject.toml`, etc. — but NOT files that the framework also has). |

## The pattern to use

**Derive `framework_root` structurally from `__file__`, not by walking.** A framework Python module always sits at a known depth inside the framework tree, so `Path(__file__).resolve().parents[N]` gives the framework root exactly. No walk, no marker, no false-positive surface.

**Derive `project_root` from `framework_root`:**

```python
def framework_root() -> Path:
    # This file is at <fr>/scripts/forge/dashboard/server.py → parents[3]
    return Path(__file__).resolve().parents[3]

def project_root() -> Path:
    fr = framework_root()
    if fr.name == ".claude":
        return fr.parent  # vendored install
    # Self-hosting (framework dev repo): walk up for `.git` only
    for p in [fr, *fr.parents]:
        if (p / ".git").exists():
            return p
    return fr
```

The `fr.name == ".claude"` check is the **structural discriminator** — it tells you "the framework is vendored, the project lives one up" without needing any marker file.

## When you create a NEW file from a framework script

Decide which root owns the file BEFORE you write it:

- **Project artifact** (task state, registry, ISA, project memory, generated code maps, visualizations, daily logs, anything the project's developers would commit / care about) → `project_root() / "docs" / …` (or wherever in the project tree)
- **Framework artifact** (specialist agent definition the user owns, framework-internal state like the preflight shim) → `framework_root() / "agents" / "specialists" / …`

The bug we just fixed shipped `docs/visualizations/` and `docs/code-map.json` to `framework_root` in some places and `project_root` in others. The hybrid was the actual fault. **One root per artifact type. Decide once. Document it.**

## Rsync excludes — the other half of this rule

Anything that is BOTH (a) generated/derived at framework dev time, AND (b) gitignored — must be rsync-excluded in `install.sh`. Otherwise the framework dev repo's copy bleeds into `<project>/.claude/` and the walk-up resolvers grab it as a marker.

Cross-check `.gitignore` against `install.sh` rsync `--exclude` lines for every framework refresh. Add a one-shot `rm -rf` on the post-rsync step for paths that previous installs leaked, so refresh actively heals past damage.

## What ships into consumer `.claude/` — the inclusion rule

`.claude/` is framework_root — CODE only. The strict test for whether a path in the framework dev repo should rsync into a consumer's `.claude/`:

> Is this path **required by framework runtime functionality** in the target project? Required means: read by a Python script, loaded by Claude Code at session start (via `settings.json` or `CLAUDE.md` `@`-import), referenced by a template at project init, or otherwise needed for the framework to *function* — not just to be *documented*.

If the answer isn't a clear yes, exclude it. The default is **exclude**, not include — every file that ships into a consumer's `.claude/` is one the consumer's dev team has to either accept as opaque framework infrastructure or read to understand. Both are costs. Charge them only when there's runtime value.

**`docs/` in particular** — the framework dev repo's `docs/` tree is framework self-documentation (code-map describing the framework, planning history, debug audits, the framework's own task ISAs). None of it is referenced by framework runtime. **None of it ships.** Consumer projects own their own `docs/` at project_root for their own data.

Top-level files like `CHANGELOG.md`, `CHEATSHEET.md`, `README.md`, `LICENSE`, `MEMORY-SCHEMA.md` DO ship — they're referenced by verify, by templates, and by hooks that read them into session context. That's the discriminator: real runtime reference vs. authored-only documentation.

**Sidecar `rules/*.local.md` files are project DATA, not framework CODE.** Framework rule files (`rules/patterns.md`, `rules/testing.md`, etc.) are framework-owned discipline — `install.sh` rsync overwrites them on every refresh. Consumer-specific examples, exceptions, and conventions belong in sidecar `rules/<name>.local.md` files alongside the framework rule. These are rsync-excluded (`--exclude='rules/*.local.md'` in both refresh paths) so they survive `install.sh --mode refresh-v3`. The pattern lets consumers extend framework rules without forking them — the framework keeps shipping its improvements to `<name>.md`, the consumer keeps owning `<name>.local.md`. Auto-load behaviour is unchanged: the `rules/*.md` glob picks up both.

## And the public-repo discriminator

When the framework repo itself goes public, an additional filter applies to what's tracked in git:

> Would an outside contributor browsing this file find user-facing value, or is this internal dev history?

Framework dev planning history (v2→v3 migration notes, dated audits, dev plans), the framework's own task ISAs, and orphan reference docs that don't have a home in the canonical 4-tier structure (`reference/`) should not be in public-facing git history. Keep them on disk (gitignored) for the framework dev's own use; don't expose them.

## Tests guard this

`tests/dashboard/test_root_resolution.py` synthesizes a vendored install on disk and asserts each false-positive marker is ignored. Add a new test there whenever you introduce a new resolver — synthetic vendored install + assert it resolves to the project root, not `.claude/`.
