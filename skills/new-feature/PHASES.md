# Phase Execution Details

## Phase 1: Discovery

**Always runs**

**Invoke (native, no external dependency):** the ISA `Interview` workflow (`skills/ISA/Workflows/Interview.md`) — a dependency-ordered design interview that resolves the feature's open design decisions in topological order and writes them into the ISA. This is the in-framework path and works on a bare clone.

**Optional fallback:** if the `superpowers:brainstorming` plugin is installed and you prefer open-ended intent exploration, `Skill tool → brainstorming` may be used instead. On a bare clone that plugin is absent (silent no-op), so prefer the native ISA Interview.

**Actions:**
1. Run the ISA Interview against the feature's ISA (or `brainstorming` if you chose the fallback and it's installed)
2. Resolve design decisions in dependency order, one at a time
3. Document understanding in the ISA `## Decisions` / `## Out of Scope` (or `docs/plans/YYYY-MM-DD-<feature>-design.md` for the fallback path)
4. Confirm scope assessment with user

**Output:** Design decisions resolved into the ISA, scope confirmed

---

## Phase 2: Design

**Runs for:** Medium, Large

**Invoke:** `@architect` via the Task tool.

**Actions:**
1. Review the discovery output
2. Identify affected components, files, and dependencies
3. Make architecture decisions (document as ADRs if significant)
4. Add design section to the plan document

**Wiring:**

```
Use the Task tool:
- subagent_type: "architect"
- description: "Design <feature> — affected components + ADRs"
- prompt: |
    Feature: <name>
    Discovery output: <path>
    Existing architecture: .claude/reference/02-architecture-and-tech-stack.md
    Prior ADRs: .claude/reference/06-architecture-decisions.md

    Identify affected components/files/dependencies. Make explicit
    architectural decisions; document significant ones as new ADRs in
    Nygard format. Append design section to the plan doc. Defer to
    existing Tier 2 docs on conflict.
```

**Output:** Architecture documented, affected files listed

---

## Phase 3: Planning

**Always runs**

**Actions:**
1. Read the design document from discovery/design
2. Break into implementation steps (small: 3-5 steps, medium: 5-10, large: 10+)
3. Order steps by dependency — foundational work first, integration last
4. Write plan to the design document
5. Populate TodoWrite with all steps

**Output:** Step-by-step plan, todos created

---

## Phase 4: Implementation

**Always runs**

**Primary guidance:** `@quality-engineer` for TDD workflow (v2 used `@tdd-guide`; folded into quality-engineer in v3 — TDD is part of the test-strategy responsibility).

**Supporting Agents:**
- `@security-boss` for security-critical features (auth, payments, data handling)

**Actions:**
1. Read `@quality-engineer` for TDD workflow guidance (Arrange/Act/Assert; the `tdd_aaa.py` validator surfaces drift on Write events)
2. Work through TodoWrite items in order
3. For each item: write test → implement → verify test passes
4. Mark todos complete as you go
5. For security-critical code, run `/security-review` (orchestrates `@security-boss` OWASP + secrets, then the business-logic-flaw pass). For features touching money / access control / multi-step state, the business-logic pass is the one that catches IDOR, race, and tampering flaws a plain OWASP review misses.

**Wiring (security-critical code only):**

```
Use the Task tool:
- subagent_type: "security-boss"
- description: "Review <feature> for security flaws"
- prompt: |
    Feature: <name>
    Trigger: <auth | payments | data-handling>
    Files changed: <list>

    Review against OWASP Top 10. Check for: input validation,
    parameterized queries, secrets handling, session/token strategy,
    CSRF/XSS protections, rate limiting where relevant. Defer to
    .claude/reference/03-security-auth-and-access.md +
    .claude/reference/08-security-model.md. Output: severity-tagged
    findings + recommended remediations.
```

**Output:** Code complete, tests passing

---

## Phase 5: Verification

**Always runs**

**Agents:**
- `@quality-engineer` for E2E tests (if feature has UI or critical user flows). v2 used `@e2e-runner`; folded into quality-engineer in v3.

**Actions:**
1. Run full test suite using the project's test command
2. Run type checks if applicable (`mypy`, `tsc`, etc.)
3. Run linting using the project's linter
4. **If feature has UI/user flows:** Invoke `@quality-engineer` to run E2E tests
5. Confirm all checks pass

**Wiring (E2E run, conditional):**

```
Use the Task tool:
- subagent_type: "quality-engineer"
- description: "Run E2E tests for <feature>"
- prompt: |
    Feature: <name>
    UI/user flows touched: <list>
    E2E framework: see .claude/reference/04-development-standards-and-structure.md

    Run E2E suite (or scoped subset matching the touched flows). Capture
    failures with screenshots/network traces where applicable. Output:
    pass/fail per flow + reproductions for any failures. Surface flaky
    tests separately from real failures.
```

**Output:** All checks green (or list of failures to address)

---

## Phase 6: Review

**Runs for:** Medium, Large

**Agents:**
- `@quality-engineer` — primary reviewer (v2's `@refactor-cleaner` was cut; refactor concerns now invoke the `/refactor` skill explicitly when warranted)

**Actions:**
1. Invoke `@quality-engineer` to review all changes made
2. Check for security issues, edge cases, code quality
3. If significant refactor opportunities surface, invoke the `/refactor` skill (risk-scaled refactor process)
4. Address any findings
5. Document review outcome

**Wiring (review):**

```
Use the Task tool:
- subagent_type: "quality-engineer"
- description: "Review <feature> changes for quality + correctness"
- prompt: |
    Feature: <name>
    Files changed: <list — from git diff>
    Test coverage report: <path or stdin>

    Review for: correctness, edge cases, error handling, test coverage
    gaps, code style adherence to .claude/reference/04-development-
    standards-and-structure.md. The `quality_coverage.py` validator
    will fire on any test-file Write — its findings are advisory
    inputs to your review. Output: per-file findings tagged
    [must-fix | should-fix | nit].
```

**Output:** Review complete, adjustments made, code quality verified

---

## Phase 7: Documentation Update

**Runs for:** Medium, Large (or if feature adds public API/config)

**Skill:** `/refresh-project-context` (v2 used `@doc-updater`; folded into the skill in v3 — doc refresh is a workflow, not an agent persona).

**Actions:**
1. Invoke `/refresh-project-context` to check if documentation needs updates:
   - README.md (new features, config options)
   - API documentation (new endpoints, changed signatures)
   - Code comments (complex logic)
   - CHANGELOG.md (add to Unreleased section)
2. Apply documentation updates
3. Verify examples in docs still work

**Output:** Documentation synchronized with implementation

---

## Phase 8: Commit

**Always runs**

**Actions:**
1. Run `git status` to see all changes
2. Run `git diff` to review changes
3. Stage relevant files (exclude unrelated changes)
4. Generate commit message following project conventions
5. Present commit message for approval
6. Commit on approval

**Output:** Changes committed
