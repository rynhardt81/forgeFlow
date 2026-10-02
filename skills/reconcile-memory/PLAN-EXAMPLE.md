# Example reconcile plan

The shape of the plan shown at step 4 of SKILL.md, before anything is applied:

```
docs/project-memory/key-facts.md — 63 618 B, over the 20 000 cap (tail already dropped)

  KEEP      12 entries  (1 403 B)   one-line facts, current
  RELOCATE   8 entries  (26 846 B)  -> decisions.md — "Technical Baseline" is
                                       decisions of record, not facts
  DELETE     1 section  (34 746 B)  -> "Current Repository State", a 2026-07-07
                                       snapshot; 6 of its 9 claims no longer
                                       match the tree. Replaced by one dated
                                       superseded line.
  RESULT    ~4 KB, fully injected, nothing truncated
```
