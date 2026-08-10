---
id: ymz3md
title: Establish the four checks when the stack lands
state: todo
priority: high
labels:
    - maintenance
created: 2026-08-08T06:42:33Z
updated: 2026-08-08T06:42:33Z
---

No code and no chosen stack exist yet, so `format`, `lint`, `typecheck`, and `test` have no commands. The entry files (`AGENTS.md`, `CLAUDE.md`) carry placeholders instead of commands.

Do this in the first session that lands a stack:

1. Set up the stack's standard tools: a formatter, a linter, a typechecker, and a test runner. Available on this machine: node/npm/pnpm, python3/uv, go.
2. Start the typechecker at **full strict**. This is a fresh project, so it is the cheapest moment there will ever be.
3. Make each of the four commands pass green on the tree. A test runner that fails on an empty suite gets one smoke test.
4. Record the four commands, and the run command, in the Checks section of `AGENTS.md`.
5. This repository has no git remote. If one is added and it is CI-capable, add a minimal workflow that runs these same four commands on push.
