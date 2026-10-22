# Framework root vs. project root — never confuse them

> **Loaded at every session start** — all of `.claude/rules/*.md` is. Binding. Keep it short: opt-in depth belongs in a skill or `reference/`. See CONTRIBUTING.md "The rules budget".

| Concept | Owns | Vendored install | Framework dev repo |
|---|---|---|---|
| **framework_root** | CODE — `skills/`, `agents/`, `hooks/`, `scripts/`, `reference/`, `rules/`, `templates/` | `<project>/.claude/` | the repo root |
| **project_root** | DATA — `docs/tasks/`, `docs/epics/`, `docs/project-memory/`, `daily/`, `ISA.md`, project `CLAUDE.md`, generated artifacts (`docs/code-map.json`, `docs/visualizations/`) | `<project>/` | the repo root (coincides) |

The roots coincide in the framework's own repo and differ in every vendored install, which is why bugs of this class pass dev-repo testing.

- **Never find a root by walking up for a marker file.** `CLAUDE.md` and `docs/code-map.json` have both stopped the walk inside `.claude/`. Derive `framework_root` structurally: `Path(__file__).resolve().parents[N]`. `project_root` is its parent when `framework_root.name == ".claude"`; otherwise walk up for `.git` only.
- **One root per artifact type, decided before the first write.** Project artifacts (task state, registry, ISA, project memory, code maps, visualizations, daily logs) go under `project_root`; framework artifacts (specialist definitions, the preflight shim) under `framework_root`. A hybrid — some writers to one root, some to the other — was the actual fault last time.
- **Sidecars are project data.** `rules/<name>.local.md` and `skills/<name>/SKILL.local.md` are rsync-excluded, survive refresh and win on conflict; framework `rules/*.md` and `SKILL.md` are overwritten.

Worked cases, the marker history, the resolver code and why skills need their own sidecar: `reference/framework-roots.md`. What ships into a consumer's `.claude/`: `CONTRIBUTING.md`.
