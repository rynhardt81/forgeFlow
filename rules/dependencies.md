# Dependency Hygiene Rules

> **Loaded at every session start.** Binding.
>
> Applies to every project that consumes Forge Flow.

Supply-chain attacks via package managers (npm Axios, Tanstack; PyPI LiteLLM,
Mistral AI) and AI-agent "slop-squatting" (hallucinated near-name packages) have
moved this from theoretical to routine. Every `pip install` / `npm install` /
`uv add` executes arbitrary code from a stranger on the machine. These four
practices apply regardless of language.

## The four principles

1. **Pin exact versions, not ranges.** No unbounded ranges in any dependency
   spec. Tomorrow's compromised release must not auto-install on the next sync.
2. **Enforce a publish cool-down window.** Refuse package versions published in
   the last 7 days (tighten to 14 for projects holding real secrets; relax to 3
   only on throwaway experiments). Most compromised releases are detected and
   yanked within 24–48 hours.
3. **Lockfile-strict in CI.** The lockfile is ground truth; CI must fail if the
   manifest and the lockfile have diverged. Default sync commands that
   "reconcile" silently are the attack vector.
4. **Every dependency earns its place.** **Never add a new dependency without
   asking first**, with a justification: what it does, why stdlib won't work,
   install surface size. For small functionality (~50 lines), prefer rewriting
   inline. This is the only defence against hallucinated package names.

How to enforce each one in uv, bun, npm and cargo (config keys, CI commands,
templates): `reference/dependencies-setup.md`.

## See also

- `templates/pyproject.toml.template` — starting a new uv project (safe defaults pre-set)
- `.claude/reference/03-security-auth-and-access.md` — a dependency that handles credentials or secrets
