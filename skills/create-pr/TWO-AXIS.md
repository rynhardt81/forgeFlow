# Two-axis review

> Step 3.7's two review axes, and the standalone `review-since <ref>` mode. The gate (what blocks) is in SKILL.md. Adapted from mattpocock/skills `code-review` (MIT) — see `THIRD-PARTY-NOTICES.md`.

## Contents

- Why two axes
- The fixed point
- Spec source
- Standards sources and the smell baseline
- The two dispatches
- Aggregate and bucket

## Why two axes

- **Standards**: does the code conform to this project's documented coding standards?
- **Spec**: does the code faithfully implement what the task asked for?

A change can pass one axis and fail the other. Code that follows every standard but implements the wrong thing → **Standards pass, Spec fail.** Code that does exactly what the task asked but breaks the project's conventions → **Spec pass, Standards fail.** Both axes run as **parallel sub-agents** so they don't pollute each other's context, and they are reported separately so one axis can't mask the other.

## The fixed point

In Step 3.7 the fixed point is the Step 2 target branch. In `review-since <ref>` mode it is whatever the user said (a SHA, branch, tag, `main`, `HEAD~5`); if they gave none, ask.

Capture the diff command once: `git diff <fixed-point>...HEAD` (three-dot, so the comparison is against the merge-base), plus `git log <fixed-point>..HEAD --oneline`. Before going further, confirm the fixed point resolves (`git rev-parse <fixed-point>`) and the diff is non-empty. A bad ref or empty diff should fail here, not inside two parallel sub-agents. Pass the ref as its own argument, never interpolated into a command string (SKILL.md → Untrusted values).

## Spec source

Look for the originating spec, in this order:

1. The forge task for this branch (`forge task show <T###>`): its body's objective, requirements and acceptance criteria, and the intent file its `Intent:` line names (**Proposed outcome** + **Constraints**).
2. The task ISA (`docs/tasks/<id>/ISA.md`): its ISCs, including `Anti:` criteria.
3. A path the user passed.
4. Nothing found → ask the user where the spec is. If there isn't one, the Spec sub-agent is skipped and the report says "no spec available".

## Standards sources and the smell baseline

Collect every file that documents how code should be written: `rules/coding-style.md` and its `.local.md` sidecar, `reference/04-development-standards-and-structure.md`, `CONTRIBUTING.md` and `CODING_STANDARDS.md` when they exist (always on the list when present), and any other standards doc the project points at.

On top of whatever the project documents, the Standards axis always carries the **smell baseline** below: a fixed set of Fowler code smells (_Refactoring_, ch. 3) that applies even when a project documents nothing. Two rules bind it:

- **The project overrides.** A documented project standard always wins; where it endorses something the baseline would flag, suppress the smell.
- **Always a judgement call.** Each smell is a labelled heuristic ("possible Feature Envy"), never a hard violation. Like any standard here, skip anything tooling already enforces.

Each smell reads *what it is* → *how to fix*; match it against the diff:

- **Mysterious Name**: a function, variable, or type whose name doesn't reveal what it does or holds. → rename it; if no honest name comes, the design's murky.
- **Duplicated Code**: the same logic shape appears in more than one hunk or file in the change. → extract the shared shape, call it from both.
- **Feature Envy**: a method that reaches into another object's data more than its own. → move the method onto the data it envies.
- **Data Clumps**: the same few fields or params keep travelling together (a type wanting to be born). → bundle them into one type, pass that.
- **Primitive Obsession**: a primitive or string standing in for a domain concept that deserves its own type. → give the concept its own small type.
- **Repeated Switches**: the same `switch`/`if`-cascade on the same type recurs across the change. → replace with polymorphism, or one map both sites share.
- **Shotgun Surgery**: one logical change forces scattered edits across many files in the diff. → gather what changes together into one module.
- **Divergent Change**: one file or module is edited for several unrelated reasons. → split so each module changes for one reason.
- **Speculative Generality**: abstraction, parameters, or hooks added for needs the spec doesn't have. → delete it; inline back until a real need shows.
- **Message Chains**: long `a.b().c().d()` navigation the caller shouldn't depend on. → hide the walk behind one method on the first object.
- **Middle Man**: a class or function that mostly just delegates onward. → cut it, call the real target direct.
- **Refused Bequest**: a subclass or implementer that ignores or overrides most of what it inherits. → drop the inheritance, use composition.

## The two dispatches

Issue both in the same message as the Step 3.7 specialist fan-out. A diff review is E2 work under the model-routing table.

```
Use the Task tool:
- subagent_type: "worker-e2"
- description: "Standards axis review"
- prompt: |
    Read-only review. Diff: git diff <fixed-point>...HEAD. Commits: <list>.
    Standards sources: <files from above>. Smell baseline: <the 12 smells and
    their two binding rules, pasted in full>.
    Report, per file/hunk where relevant, (a) every place the diff violates a
    documented standard: cite the standard (file + the rule); and (b) any
    baseline smell you spot: name it and quote the hunk. Distinguish hard
    violations from judgement calls: documented-standard breaches can be hard,
    but baseline smells are always judgement calls, and a documented project
    standard overrides the baseline. Skip anything tooling enforces. Under 400 words.
```

```
Use the Task tool:
- subagent_type: "worker-e2"
- description: "Spec axis review"
- prompt: |
    Read-only review. Diff: git diff <fixed-point>...HEAD. Commits: <list>.
    Spec: <task body / intent / ISA ISCs, path or contents>.
    Report: (a) requirements the spec asked for that are missing or partial;
    (b) behaviour in the diff that wasn't asked for (scope creep); (c)
    requirements that look implemented but where the implementation looks
    wrong. Quote the spec line for each finding. Under 400 words.
```

If the spec is missing, skip the Spec dispatch and note it in the report.

## Aggregate and bucket

Present the two reports under `## Standards` and `## Spec` headings, verbatim or lightly cleaned. Do **not** merge or rerank findings across the axes. End with a one-line summary: total findings per axis, and the worst issue _within each axis_ (if any). Don't pick a single winner across axes: that's the reranking the separation exists to prevent.

For the Step 3.7 push gate, each finding also gets a bucket:

| Finding | Bucket |
|---|---|
| Spec (a) missing / (c) wrongly implemented requirement, or a missed intent outcome/constraint | `MUST-FIX` |
| Spec (b) scope creep | `NICE-TO-HAVE` (`MUST-FIX` when it touches schema, auth, money or security) |
| Standards: hard violation of a documented standard | `MUST-FIX` or `NICE-TO-HAVE`, by the standard's own severity |
| Standards: baseline smell | `NICE-TO-HAVE` at most — a smell never blocks a PR by itself |
