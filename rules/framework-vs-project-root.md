# Framework root vs. project root — never confuse them

> **Loaded at every session start** — all of `.claude/rules/*.md` is. Binding. Keep it short: opt-in depth belongs in a skill or `reference/`. See CONTRIBUTING.md "The rules budget".

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

## Sidecars — how a project extends a framework file without forking it

**Sidecar `rules/*.local.md` files are project DATA, not framework CODE.** Framework rule files (`rules/patterns.md`, `rules/testing.md`, etc.) are framework-owned discipline — `install.sh` rsync overwrites them on every refresh. Consumer-specific examples, exceptions, and conventions belong in sidecar `rules/<name>.local.md` files alongside the framework rule. These are rsync-excluded (`--exclude='rules/*.local.md'` in both refresh paths) so they survive `install.sh --mode refresh-v3`. The pattern lets consumers extend framework rules without forking them — the framework keeps shipping its improvements to `<name>.md`, the consumer keeps owning `<name>.local.md`. Auto-load behaviour is unchanged: the `rules/*.md` glob picks up both.

**Sidecar `skills/<name>/SKILL.local.md` files are the same pattern for skills.** A framework skill is framework-owned; the rsync overwrites `SKILL.md` on every refresh. Project-specific guidance for that skill belongs in `SKILL.local.md` beside it, which is rsync-excluded and survives refresh.

Skills need their own sidecar because neither existing mechanism reaches them:

- `rules/<name>.local.md` auto-loads via the `rules/*.md` glob, but most skills never read `rules/` at all (`/create-pr` doesn't), so skill-specific guidance parked in a rule sidecar is never seen at the moment it applies.
- `skills/<name>.local/` is a *separate* skill, not an extension — it can't add a step to `/create-pr`.

Nothing globs skill files, so **the pointer line at the end of each framework `SKILL.md` IS the discovery mechanism** — the agent reads it while following the skill and loads the sidecar. Keep that line when editing a skill.

Precedence: **the sidecar wins on conflict.** The project owns its own policy. One obligation attaches — a sidecar that *relaxes a gate* the framework skill defines must state how to prove the gate is wrong in that case, so the relaxation is falsifiable rather than a silent opt-out. The pattern that motivated this rule did it unprompted:

> Before overriding, PROVE it's the wrong gate: `git diff --name-only origin/main...HEAD | grep -iE '\.github/workflows/|frontend/'` — if that matches, do NOT skip.

Why this exists: a consumer added project-specific push policy directly to the framework's `create-pr/SKILL.md` — the only place it would reliably be read — and a routine refresh correctly overwrote it. Framework files are framework-owned; the sidecar is where that content survives.

---

**Authoring the framework rather than using it?** The rules for what rsyncs into a consumer's `.claude/`, the exclude cross-check, the public-repo filter and the resolver tests live in `CONTRIBUTING.md` → "What ships into a consumer's `.claude/`". They were moved out of here because every consumer session was loading them at startup to answer a question only a framework developer asks.
