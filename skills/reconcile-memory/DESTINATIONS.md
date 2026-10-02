# Destinations for relocated memory

## Two destinations, and why the obvious one is not always right

`MEMORY-SCHEMA.md` routes by kind — bugs to `bugs.md`, decisions to `decisions.md`, conventions to `patterns.md`. Those three are read on demand, so an entry moved there costs nothing at startup and stays findable.

**But the index is injected, and every entry in those three files earns a line in it.** `forge memory reindex` builds `index.md` from their entry headings, and `index.md` loads at every SessionStart alongside `key-facts.md`. So relocation is not free: it converts a large per-session cost into a small one, roughly 100 bytes of index per entry, not into zero.

That is fine for entries. It is the wrong move for bulk. Measured on a 63 KB key-facts.md: routing 21 blocks by kind shrank the injected total to 11 142 B, while lifting the same two sections out whole to non-indexed files reached 8 024 B — the index growth ate a fifth of the saving, and the second approach also kept the material verbatim instead of chopping it into entries it was never written as.

So choose by shape:

| What you are moving | Where it goes | Why |
|---|---|---|
| An individual fact, decision, bug or convention | `decisions.md` / `bugs.md` / `patterns.md` | Indexed, findable, ~100 B/session for the index line |
| A whole coherent section — an architecture baseline, a repo-state chronology, a design of record | `docs/project-memory/reference/<topic>.md`, moved **verbatim** | `memory_index.py` scans only the three entry files, so this is invisible to the index and costs literally nothing per session |

Leave exactly one line in `key-facts.md` pointing at a file you moved wholesale, so a reader still knows it exists. `docs/**` is excluded from the refresh rsync, so this destination is project data that survives a framework refresh untouched.

`.claude/reference/` (Tier 2) is a legitimate home for material that is genuinely "what the system IS" rather than a remembered fact, and populated `NN-*.md` files there survive refresh because the framework only ships the `NN-*.template.md` variants. But that is a documentation-governance decision with an ADR attached, so **propose it and let the user choose** — do not move anything there unprompted.

**Where this skill stops:** age-based cleanup within `bugs.md` / `decisions.md` / `patterns.md` belongs to `/remember archive`, which already does it. Reconcile decides *which file* an entry belongs in; archive decides *whether it is still current*. If you finish and the destination files are themselves stale, say so and suggest `/remember archive` — don't reimplement it.
