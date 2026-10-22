# Domain Docs

> How skills consume the project's domain documentation when exploring the codebase. Kept current by `/domain-modeling`. Adapted from mattpocock/skills `setup-matt-pocock-skills/domain.md` (MIT) — see `THIRD-PARTY-NOTICES.md`.

## Before exploring, read these

- **`GLOSSARY.md`** at the project root, or
- **`GLOSSARY-MAP.md`** at the project root if it exists: it points at one `GLOSSARY.md` per context. Read each one relevant to the topic.
- **`reference/06-architecture-decisions.md`**: read the ADRs that touch the area you're about to work in.

If any of these don't exist, **proceed silently**. Don't flag their absence; don't suggest creating them upfront. `/domain-modeling` (reached via `/grilling --docs` and the architecture survey) creates the glossary lazily when terms actually get resolved.

## Use the glossary's vocabulary

When your output names a domain concept (in a task title, a refactor proposal, a hypothesis, a test name, a PR body), use the term as defined in `GLOSSARY.md`. Don't drift to synonyms the glossary explicitly avoids.

If the concept you need isn't in the glossary yet, that's a signal: either you're inventing language the project doesn't use (reconsider) or there's a real gap (note it for `/domain-modeling`).

## Flag ADR conflicts

If your output contradicts an existing ADR, surface it explicitly rather than silently overriding:

> _Contradicts ADR-007 (event-sourced orders), but worth reopening because…_
