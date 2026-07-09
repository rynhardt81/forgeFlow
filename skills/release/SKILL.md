---
name: release
description: Release workflow — analyzes conventional commits, infers version bumps, runs pre-release checks and a release-safety checklist (rollback verified, staged rollout, feature-flag inventory), updates CHANGELOG.md, creates git tags, publishes GitHub Releases, and probes the release post-publish. Handles pre-releases (alpha/beta/rc) and hotfixes. Trigger keywords — release, publish, ship, version bump, tag, changelog, semver, cut a release.
---

# Release

Doctrine home: `rules/release-engineering.md` — read it when it exists in the project; this skill implements its workflow.

## Invocation

`/release` (infer bump from commits) · `/release patch|minor|major` (force) · `/release --pre alpha|beta|rc` (pre-release: `1.3.0-beta.1`, subsequent runs increment `beta.N`) · `/release --skip-checks` (emergency only — requires explicit confirmation, logs the skip in the release notes).

## Workflow

1. **Analyze** — current version, commits since last tag, inferred bump.
2. **Verify** — pre-release checks + release-safety checklist (below).
3. **Update** — bump version files (including the framework's own `VERSION` file, if present at repo root), finalize CHANGELOG.md, commit.
4. **⛔ Gate 1: confirm before tag** — show version bump (old → new), changelog entry, check results. User approves or adjusts. This is the last cheap exit; everything before this is a local commit.
5. **Tag** — annotated tag (`git tag -a v<X.Y.Z> -m "..."`, never lightweight), push.
6. **⛔ Gate 2: confirm before publish** — GitHub Release + deployment are public/irreversible. Show release notes and deploy plan; user approves.
7. **Publish + deploy** — `gh release create` with notes from the changelog entry (mark `--prerelease` when applicable); trigger or checklist the deployment per project config.
8. **Post-release probe** — see Release safety.

These are the only two confirmation gates. Everything else reports inline and proceeds.

## Version bump inference (conventional commits)

| Signal | Bump | Changelog category |
|--------|------|--------------------|
| `!` suffix or `BREAKING CHANGE:`/`BREAKING-CHANGE:` footer | **Major** | Breaking Changes |
| `feat:` | Minor | Added |
| `remove:` | Minor | Removed |
| `fix:`, `revert:` | Patch | Fixed |
| `perf:`, `refactor:`, `build:` | Patch | Changed |
| `deprecate:` | Patch | Deprecated |
| `security:` | Patch | Security |
| `docs:`, `style:`, `test:`, `chore:`, `ci:` | none | excluded |

Highest-priority signal across all commits wins. Skip merge commits, `wip:`, and prior `chore(release):` commits. Get commits with `git log $(git describe --tags --abbrev=0 --match "v*")..HEAD --no-merges --pretty=format:"%s|%b"`. Non-conventional commits go to a "Miscellaneous" section or are skipped with a warning. Extract issue refs (`#123`, `fixes #123`) into changelog entries.

## Version file detection

Priority: explicit `version_files` in `.release-config.json` → auto-detect → prompt. Auto-detect order: `package.json` → `pyproject.toml` → `Cargo.toml` → `VERSION` → `setup.py` → others (`build.gradle`, `pom.xml`, `mix.exs`, `pubspec.yaml`). Multi-file projects (monorepo, frontend+backend): all files bump to the same version; if they currently disagree, report the conflict and ask which is the base. Validate: current is valid semver, new > current (unless pre-release).

## Pre-release checks

All must pass before Gate 1:

| Check | Probe |
|-------|-------|
| Tests | project test command (from `.release-config.json` `checks`, else auto-detect: Makefile `test` / `package.json` / `pytest` / `cargo test` / `go test ./...`) |
| Types / Lint | project commands, same detection pattern |
| Clean tree | `git status --porcelain` empty |
| Branch | on `main`/`master`/`release/*` (override via config `allowed_branches`) |
| Remote sync | `git fetch` then not behind remote |

On failure: report which check failed with its output, then fix-and-retry or abort — never proceed. Build/CI failures route to `@devops` (Task tool) for diagnosis.

## Release safety (pre-Gate-1 checklist)

Report each item's status explicitly — "not applicable" is a valid answer, silence is not:

1. **Rollback identified AND verified runnable** — name the exact command for this deploy target (`eas update --rollback`, platform equivalent, or a `git revert <tag-commit>` + redeploy plan) and prove it's runnable now (command exists, credentials present — e.g. `eas whoami`, `gh auth status`). A rollback you discover is broken during an incident is not a rollback.
2. **Staged rollout for store apps** — releases through an app store set a staged-rollout percentage (e.g. 10% → 50% → 100%) rather than full-blast; state the starting percentage and the promotion criterion.
3. **Feature-flag inventory** — list flags/dormant code paths this release touches and answer: *what's dormant that this release could accidentally wake?* (config defaults changed, dead code now reachable, a paywall or experiment flag flipping). Verify each stays in its intended state.
4. **Post-release probe planned** — name the probe to run after publish: hit the health endpoint, open the store listing, `curl` the deployed version endpoint. After deploy, actually run it and show the output — the release isn't done until the probe passes.

## Changelog

Keep a Changelog format, semver. `## [Unreleased]` section at top; on release, move its content to `## [X.Y.Z] - YYYY-MM-DD`. Section order (only non-empty sections): **Breaking Changes** (always first), Added, Changed, Deprecated, Removed, Fixed, Security. Entries: capitalized, no trailing period, one line, `(#123)` refs where available; group by scope with bold sub-headers only when a section is large. Maintain comparison links at the bottom (`[X.Y.Z]: .../compare/vA...vB`). GitHub Release notes reuse the same section content.

## Documentation audit

Before Gate 1, invoke `/refresh-project-context`: finalize CHANGELOG, verify README/API docs match the implementation, create a migration guide for breaking changes. Surface findings inline; only genuine gaps block.

## PR-first option

Where release-prep commits are reviewed before shipping, invoke `Skill("create-pr")` BEFORE tagging — the reviewer merges the version-bump/changelog PR, then tagging proceeds from the release branch. Per-project default via `prFirst: true|false` in `.release-config.json`; absent the flag, ask once on first release. Never raw `gh pr create`.

## Configuration

`.release-config.json` (optional): `version_files`, `checks` (custom commands), `allowed_branches`, `prFirst`, deployment mode/checklist, GitHub Release options. Without it, auto-detect and confirm.

## Key rules

- Never release with failing checks or a dirty tree.
- Annotated tags only; CHANGELOG updated before tagging.
- Two gates: before tag, before publish. No other confirmation stops.
- The release isn't done until the post-release probe passes with shown output.
