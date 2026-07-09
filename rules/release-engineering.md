# Release Engineering Rules

> Active directive. Discovered on-demand via the `rules/*.md` glob — read by `/audit-rules`, the `/release` skill, and any agent shipping to users. Treat as binding when encountered. The tag is where the framework's old release story ended — and where user-facing risk begins. These rules cover the part after the tag.

## The three questions every release answers BEFORE it ships

1. **How do we roll this back?** Name the exact command/mechanism for THIS deploy target and confirm it's runnable now — not in the incident:
   - Expo/EAS OTA: `eas update --branch <channel> --republish` to the previous update (know the previous update's group ID before shipping)
   - Store binary: staged rollout halt + previous binary remains live (you cannot un-ship a binary — see staged rollout below)
   - Vercel/serverless: instant rollback to the previous deployment (`vercel rollback` / dashboard promote)
   - Database: the paired down-migration or recovery note (`rules/migrations.md` — schema changes make rollback asymmetric; expand/contract keeps app rollback safe)
2. **Who gets it first?** Default to staged exposure for anything user-facing:
   - Play Store: staged rollout percentage (start 10–20%, watch crash rate + vitals before 100%)
   - App Store: phased release on
   - Web: preview → production promote, not direct-to-prod
3. **How will we know it's healthy?** Name the post-release probe before releasing: crash-free rate threshold, health endpoint check, the one user flow you'll manually verify. A release without a named health signal is a release you can't declare successful.

## Feature flags

- A dormant capability shipping ahead of its activation (paywall, new flow, pricing) is a **feature flag** — treat it as one: it appears in a flag inventory (a section in `reference/05-operational-and-lifecycle.md`), with its current state, flip condition, and owner.
- Every release checks the inventory: "does this release accidentally wake anything dormant?"
- Flipping a flag IS a release — it gets the same three questions above (rollback = flip back; verify the flip-back actually works before flipping forward).
- Kill stale flags: a flag fully-on for two releases becomes dead code to remove.

## DO / DON'T

- **DO** cut releases from a green local gate (`/preflight-ci`) when CI is unavailable — the gate of record is whichever actually ran.
- **DO** write the changelog entry from the user's perspective (what changed for them), not the diff's.
- **DO** verify the release artifact itself once live (install from the store track / hit the deployed URL) — "the pipeline succeeded" is not "users have it".
- **DON'T** ship schema changes and their dependent app changes as one atomic all-or-nothing release — expand/contract across releases (`rules/migrations.md`).
- **DON'T** release significant changes at the end of your working window with no time to watch the health signal.
- **DON'T** bump version numbers by hand when the `/release` skill derives them — one source of truth.
