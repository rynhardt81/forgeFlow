# Code Patterns Rules

> Active directive. Discovered on-demand via the `rules/*.md` glob — read by `/audit-rules` and any agent reasoning about code patterns. Treat as binding when encountered.

## API Response Format

**The codebase's response shape is whatever each route's declaration says it is. Schema class existence is NOT the source of truth — dead schema classes lie.**

Real codebases past their first epic accumulate multiple coexisting response shapes (legacy bare, envelope, hybrid, plain list, single-item variants). An enumeration in markdown becomes a load-bearing lie on the first refactor that doesn't update it. Don't write one.

### Before touching any endpoint

1. **Grep the route file for the declared shape.** Stack-specific marker:
   - FastAPI / Pydantic: `response_model=`
   - Express / NestJS: `res.json(` or `@ApiResponse` / `@Returns`
   - Go (stdlib / gin / echo): the final `c.JSON(` or `json.NewEncoder(w).Encode(`
   - Rails: the controller's `render json:` / serializer class
   - Phoenix / Plug: the final `json(conn, ...)`
2. **Grep the frontend caller for the extraction pattern.** Frontends are coupled per-route; whatever the frontend reads out is part of the contract.
3. **Match what's already there.** Don't introduce a new shape unless the task is an explicit, frontend-coordinated migration.

### Brand-new greenfield endpoints

For genuinely new domains where no contract exists yet, prefer an envelope (e.g. `APIResponse[T]` / `APIListResponse[T]` if the project ships such a helper). That's the safer direction of travel — but it's a starter default, not a project-wide truth.

### Never

- Retrofit a working endpoint's shape without a frontend-coordinated migration task.
- Trust that "the schema class exists, so this is the shape" — unused schema classes outlive their usage.
- Paste a shape catalog into this file and treat it as canonical. Every new commit can falsify it; nobody re-runs the audit.

### Error response

Most projects do converge on a single error-shape convention (structured detail with `code` + `message` + optional `field` map). If yours does, fill it in here. If not, the same grep-first rule applies.

## Validation

Schema validation (Zod, Pydantic, Joi, equivalent) at every API boundary.

## Project-specific extensions

Add project-specific examples, exceptions, and conventions to `rules/patterns.local.md` alongside this file. Sidecar `*.local.md` files are excluded from framework refresh — they survive `install.sh --mode refresh-v3`. Readers (skills, agents, `/audit-rules`) pick up both via the `rules/*.md` glob.

## See also

- `.claude/reference/04-development-standards-and-structure.md` — project conventions including error handling, async patterns, React, database
