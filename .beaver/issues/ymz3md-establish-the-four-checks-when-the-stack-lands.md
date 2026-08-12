---
id: ymz3md
title: Establish the four checks when the stack lands
state: todo
priority: high
labels:
    - maintenance
created: 2026-08-08T06:42:33Z
updated: 2026-08-12T05:16:55Z
---

No code and no chosen stack exist yet, so `format`, `lint`, `typecheck`, and `test` have no commands. The entry files (`AGENTS.md`, `CLAUDE.md`) carry placeholders instead of commands.

Do this in the first session that lands a stack:

1. Set up the stack's standard tools: a formatter, a linter, a typechecker, and a test runner. Available on this machine: node/npm/pnpm, python3/uv, go.
2. Start the typechecker at **full strict**. This is a fresh project, so it is the cheapest moment there will ever be.
3. Make each of the four commands pass green on the tree. A test runner that fails on an empty suite gets one smoke test.
4. Record the four commands, and the run command, in the Checks section of `AGENTS.md`.
5. This repository has no git remote. If one is added and it is CI-capable, add a minimal workflow that runs these same four commands on push.

## Notes

**claude** — 2026-08-12T04:50:20Z

STACK FACT from the 7mfxzj prototype session (2026-08-12), recorded here because this issue owns the stack: the frontend will be built with shadcn/ui over Tailwind. The user stated it directly while approving the app-shell prototype.

7mfxzj's note carries the consequence in full. The part that binds this issue: shadcn ships only --destructive as a semantic colour, so the app's semantic ramp (--wait "a human is needed", --human "a secret", --ok) is an ADDITION to the theme in globals.css, not something the library provides. The surfaces and ink map onto shadcn's own names (--bg->--background, --panel->--card, --ink->--foreground, --mut->--muted-foreground, --line->--border, --accent->--primary), and the spacing and radius scales settled by 7mfxzj are Tailwind defaults already (4/6/8/12/16/24 = 1/1.5/2/3/4/6).

This does not settle the rest of the stack. The framework version, monorepo layout, dev environment, and the four check commands this issue exists to establish are still open.

**claude** — 2026-08-12T05:16:55Z

STACK FACT, from spec `pc0t8s` (roadmap node smpcpi): the frontend takes TANSTACK QUERY for server state, alongside the shadcn/ui-over-Tailwind choice already recorded here from 7mfxzj. It earns its place on deduplication of GET /api/auth/me across the shell, visibility-aware polling with refetch-on-focus for GET /api/attention, and invalidation after mutations — starting or cancelling a Run makes both the attention key and the Runs list key stale at once, and the run detail's SSE stream invalidates the same keys.

TWO DEFAULTS ARE MANDATED, not inherited from the library:
- mutations: {retry: false}. A retried POST /api/workflows/{id}/runs or POST /api/schedules/{id}/run-now is a second Run acting on a real website — the hazard nno9gj's 'two copies never act at once' invariant exists to prevent. This is the one place ADR 0002's spirit reaches the HTTP layer.
- query retry and staleTime chosen explicitly per key rather than taking the library's defaults.

For the record, since the first draft of pc0t8s got this wrong and the user corrected it: ADR 0002 forbids automatic retries of a RUN, which is not idempotent and acts on external sites. Refetching our own read endpoints is a different hazard, and only the mutation default touches the ADR's territory. Do not re-argue the rejection.

Also from pc0t8s, for whoever lands this issue: no date library (Intl.RelativeTimeFormat and Intl.DateTimeFormat cover relative times and per-timezone rendering), and Seam 2 of that spec needs a frontend test runner able to exercise a pure module — resolveGate — with no browser and no DOM.
