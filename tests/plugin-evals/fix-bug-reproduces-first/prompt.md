---
description: /fix-bug Gate A — the failure is reproduced by running something before the first edit, and a regression test is written.
tags: [gate, fix-bug]
max_turns: 30
timeout_seconds: 600
allowed_tools: [Read, Glob, Grep, Skill, Bash, Edit, Write]
---

There's a bug: login returns 500 for users with an apostrophe in their surname, like O'Brien. The code is in app.py. Fix it.
