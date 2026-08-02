# AGENTS.md

Instructions for AI code reviewers working in this repository.

Reviewers that read this file automatically pick it up from the repo root —
Codex does, and it is the closest thing to a cross-tool convention. Both the
local pre-push review and the post-PR cloud review read the *same* file, so
anything written here steers both passes.

> Seeded by Forge Flow because this project has a review bot configured
> (`git config forge.reviewBot` / `forge.localReview`). It is **project data**:
> a framework refresh never overwrites it. Fill it in and delete this note.
>
> `/setup-review-bot` populates the sections below from a short interview.

## Authoritative documents

<!-- Which files decide a disagreement, in priority order. A reviewer that does
     not know this argues from the wrong source and files confident wrong
     findings. -->

- 
- 

## What counts as MUST-FIX here

<!-- Be specific to THIS repo. "Bugs" is not useful; "a write path that can
     drop a record without an error" is. The reviewer's default severity model
     is generic — this is where you make it yours. -->

- 
- 

## What to skip

<!-- Areas where findings are noise: generated files, vendored code, a module
     mid-rewrite, a convention that looks wrong but is deliberate. Say WHY, or
     the next reviewer re-reports it. -->

- 
- 

## Conventions that differ from the obvious default

<!-- Things the code alone would teach wrongly. If a reviewer would flag your
     deliberate pattern as a mistake, name it here. -->

- 
