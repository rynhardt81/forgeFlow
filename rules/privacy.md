# Data Privacy Rules (POPIA / GDPR)

> Active directive. Discovered on-demand via the `rules/*.md` glob — read by `/audit-rules`, `/new-project` discovery, and any agent touching personal data. Treat as binding when encountered. Written POPIA-first (South Africa's Protection of Personal Information Act — a real regulator with real enforcement); the discipline satisfies GDPR-shaped laws generally.

## When this rule fires

Any work touching: user accounts, profiles, behavioural/usage data, **children's data** (special personal information under POPIA §34–35 — consent from a competent person/guardian is required), **health data** (special PI — pharma/medical contexts), location, contacts, payment identity, or any identifier tied to a natural person.

## The data inventory — the non-negotiable artifact

`reference/03-security-auth-and-access.md` MUST contain a data inventory table for any project processing personal data:

| Data element | Category (ordinary / special / children's) | Purpose | Lawful basis / consent | Where stored | Retention | Shared with |
|---|---|---|---|---|---|---|

A feature that adds a new personal-data element updates this table in the same PR — the inventory lying is worse than the inventory missing.

## DO / DON'T

- **DO** collect the minimum: every collected element needs a purpose you can state in one sentence (POPIA minimality principle). "Might be useful later" fails.
- **DO** flag children's data explicitly: apps used by children need guardian consent flows, no behavioural advertising, and extra care in what's logged. If the app's users include under-18s, say so in the inventory and treat their data as special PI.
- **DO** default retention: define it per element (e.g., "account data: life of account + 30 days; analytics: 90 days rolling"). Indefinite retention is a decision someone must own in writing, not a default.
- **DO** make deletion real: account deletion removes or anonymizes the person's data within the stated window — probe it (create → delete → `SELECT` returns nothing personal).
- **DO** support subject access: you can produce "everything we hold about user X" with a query, not a forensic investigation. If you can't, the schema needs a user-id spine.
- **DON'T** log personal data (`rules/observability.md` no-PII rule) — user IDs are fine, names/emails/tokens/content are not.
- **DON'T** ship personal data to third-party services (analytics, crash reporting, AI APIs) without listing that flow in the inventory's "Shared with" column and checking the processor's terms.
- **DON'T** move personal data across borders (e.g., SA → US-hosted service) without noting it — POPIA §72 conditions apply; usually fine with adequate contracts, but it must be a recorded decision.

## Breach basics

If personal data is exposed: contain, assess scope with queries (which rows/users), record a timeline, and notify per the applicable law (POPIA: the Information Regulator and affected subjects "as soon as reasonably possible"). Keep the postmortem in `docs/debug/` — breaches are incidents (`/triage-incident`).

## New-project hook

`/new-project` discovery asks: *"Will this handle personal data? Children's? Health?"* — a yes populates the inventory skeleton in `reference/03` and adds a standing `Anti:` ISC to the project ISA: "Anti: personal data element exists that is not in the data inventory."
