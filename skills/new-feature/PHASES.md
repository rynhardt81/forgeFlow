# Phase Execution Details

## Phase 1: Discovery

**Always runs**

**Invoke (native, no external dependency):** the ISA `Interview` workflow (`skills/ISA/Workflows/Interview.md`) — a dependency-ordered design interview that resolves the feature's open design decisions in topological order and writes them into the ISA. This is the in-framework path and works on a bare clone.

**Optional fallback:** if the `superpowers:brainstorming` plugin is installed and you prefer open-ended intent exploration, `Skill tool → brainstorming` may be used instead. On a bare clone that plugin is absent (silent no-op), so prefer the native ISA Interview.

**Actions:**
1. Run the ISA Interview against the feature's ISA (or `brainstorming` if you chose the fallback and it's installed)
2. Resolve design decisions in dependency order, one at a time
3. Document understanding in the ISA `## Decisions` / `## Out of Scope` (or `docs/plans/YYYY-MM-DD-<feature>-design.md` for the fallback path)

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
2. Break the work into steps ordered by dependency — foundational work first, integration last
3. Write the plan to the design document; track it in the todo list if that helps

**Output:** Step-by-step plan

---

## Phase 4: Implementation

**Always runs**

**Discipline:** test-first, Arrange/Act/Assert (the `tdd_aaa.py` validator surfaces drift on Write).

**Supporting Agents:**
- `@security-boss` for security-critical features (auth, payments, data handling)

**Actions:**
1. Work through the plan in order
2. For each step: write test → implement → verify test passes
3. For security-critical code, run `/security-review` (orchestrates `@security-boss` OWASP + secrets, then the business-logic-flaw pass). For features touching money / access control / multi-step state, the business-logic pass is the one that catches IDOR, race, and tampering flaws a plain OWASP review misses.

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
- `@quality-engineer` for E2E tests (if feature has UI or critical user flows).

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
- `@quality-engineer` — primary reviewer; significant refactor concerns go to the `/refactor` skill

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

**Skill:** `/refresh-project-context`.

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
Commit only the files this feature changed, with a message following project conventions. The commit message is shown at the before-PR confirmation (SKILL.md Step 3); no separate approval stop.

**Output:** Changes committed
