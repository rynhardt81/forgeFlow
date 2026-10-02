# Rationale

## Why memory size is a tax

**The failure it exists to stop is not "the file got big".** It is content that was never memory-shaped landing in a memory file and then being loaded whole at every startup — a repo-state snapshot, an architecture write-up, a postmortem narrative. Those are real knowledge and must survive; they just belong somewhere nothing injects. A 6 KB key-facts.md of one-line facts is healthy. A 6 KB narrative is not, at any size.

## Why restraint (step 2 of SKILL.md)

This matters because the pull is entirely one way. Nothing about a reconcile rewards leaving things alone, so the temptation is to find *something* to cut and call it progress. Measured: on an already-healthy 8 KB store, a reconcile pass trimmed it to 70% of its original size while a plain reading of the same store trimmed it to 88% — the extra cutting bought nothing a session would notice and spent judgment on entries that were fine. A reconcile that reports "already healthy, three entries could be tightened, none of it worth your time" is a complete and successful run.

Measured: a pass that stubbed four false entries and declined two obvious merges saved 43 bytes, against 1 437 bytes for the same store handled with merges — the diagnosis was better and the outcome was not.
