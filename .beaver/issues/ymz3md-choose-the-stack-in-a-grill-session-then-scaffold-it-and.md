---
id: ymz3md
title: Choose the stack in a grill session, then scaffold it and establish the four checks
state: done
assignee: claude
priority: high
labels:
    - maintenance
created: 2026-08-08T06:42:33Z
updated: 2026-08-14T05:21:14Z
---

No code and no chosen stack exist yet, so `format`, `lint`, `typecheck`, and `test` have no commands. The entry files (`AGENTS.md`, `CLAUDE.md`) carry placeholders instead of commands.

This issue is **two phases, in this order**. The stack is not a set of defaults to be picked while scaffolding: every later session inherits the layout, the runners, and the four commands, so they are interviewed first and written down, and only then built.

## Phase 1 — Grill: settle the stack

Invoke the `grill-me` skill. Interview until each question below has an answer, and record the answers on this issue before any file is written. The six published specs and the Notes below are the input; nothing here re-opens a decision they already made.

Open questions:

1. **Monorepo layout.** Which packages exist, and where. The system has at least four deployables — the Next.js frontend, the FastAPI backend, the Playwright Worker, and the MV3 extension — and `px25yw` settled that they ship as one docker compose stack (backend, Workers, Postgres, Redis, MinIO). Open: whether the Worker is its own package or a mode of the backend package, whether the extension lives in this repository at all, and what the directory names are.
2. **Which packages exist at scaffold time.** All of them, empty, or only the ones the first slices touch — and what a check command does about a package that does not exist yet.
3. **Package managers and version pinning.** npm vs pnpm vs a workspace-less layout on the TypeScript side; uv vs pip on the Python side. Whether Node and Python versions are pinned in-repo, and how.
4. **The single entry point for the four checks.** Two languages means each check spans two toolchains. Open: a `Makefile`, root package scripts, a task runner, or four scripts — and whether one failing package fails the whole command.
5. **The Python toolchain.** Formatter, linter, typechecker, test runner, and the FastAPI and Python versions.
6. **The TypeScript toolchain.** Formatter and linter (and whether one tool does both), plus the Next.js and React versions.
7. **What "full strict" means concretely,** on both sides: the exact TypeScript compiler flags beyond `strict`, and the typechecker's strictness settings on the Python side. Deciding this at scaffold time is the whole point of doing it now.
8. **The frontend test runner.** It must exercise a pure module with no browser and no DOM — `pc0t8s`'s Seam 2 (`resolveGate`) is the case that proves it.
9. **The database migration tool,** and whether the first migration is part of this issue or of the first slice that needs a table.
10. **What "run the app locally" means,** and whether the docker compose file lands here or with the first slice that needs a service running.
11. **The test tiers.** Whether a tier that touches Postgres or Redis exists from the start, how it is separated from the fast tier, and which tier the `test` command runs.

## Phase 2 — Scaffold and land the checks

With Phase 1 recorded:

1. Scaffold the packages that Phase 1 named, with the tools it chose.
2. Set the typechecker to the strictness Phase 1 defined. This is a fresh project, so it is the cheapest moment there will ever be.
3. Make each of the four commands pass green on the tree. A test runner that fails on an empty suite gets one smoke test.
4. Record the four commands, and the run command, in the Checks section of `AGENTS.md`, replacing the placeholder section wholesale.
5. Record the layout and the seams in `docs/ARCHITECTURE.md`, which is currently a header and one sentence.
6. This repository has no git remote. If one is added and it is CI-capable, add a minimal workflow that runs these same four commands on push.

## Constraints already fixed

The Notes below carry three decisions that Phase 1 takes as given and does not re-argue: shadcn/ui over Tailwind, TanStack Query with `mutations: {retry: false}`, and no date library.

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

**claude** — 2026-08-12T06:42:57Z

SESSION ORDER, set by the user on 2026-08-12: this issue is a grill session first, then a scaffold session. A scaffold was started this day without the interview — a pnpm workspace with a create-next-app frontend — and was reverted in full at the user's request, with nothing committed. The reason it was reverted stands as the reason for Phase 1: monorepo layout, task runner, and test runners are inherited by every later session, so they are interviewed and recorded, not picked while typing.

**claude** — 2026-08-14T05:15:27Z

PHASE 1 SETTLED (grill session, 2026-08-14). The stack, decided by interview; the template is the user's ../alloy repo (FastAPI + Next.js + generated typed API client, pnpm/Vite+/uv/ruff/ty/pytest).

1. Template: copy alloy's tracked tree into this repo (minus .git, caches, lockfile regen after rename), keeping this repo's history, docs, tracker, README, LICENSE.
2. Naming: full step_by_step spelling — Python package step_by_step_api, npm scope @step-by-step (e.g. @step-by-step/api-client).
3. Layout: apps/web (Next 16 / React 19.2), apps/api (FastAPI >=0.115, Python 3.14), packages/api-client (generated from OpenAPI, committed, CI contract job fails on drift), tsconfig/ presets. Later, each with its first slice: apps/worker (own uv workspace member, depends on the api package for shared models; escape hatch if awkward = extract a packages/ Python core lib) and apps/extension (MV3, covered by the workspace globs). "worker" not "browser-worker": the glossary's Worker already means the browser-holding Run executor.
4. Scaffold scope: only web, api, api-client now. Absent packages cost nothing — vp/uv iterate over existing members only.
5. Toolchains: pnpm + Vite+ (TS 7 tsgo, vp check = format + type-aware lint + typecheck, vp test = Vitest) and uv + ruff (format+lint, rules E,F,I,UP,B,SIM,RUF) + ty + pytest. Node 24, Python 3.14, pinned in-repo (.node-version, .python-version, packageManager, engineStrict). Supply-chain policy, Dependabot, SHA-pinned CI, tracked pre-commit hook — all kept from alloy.
6. The four checks: format/lint/typecheck all = pnpm check (fix: pnpm check:fix); test = pnpm test. Run locally = pnpm dev (FastAPI :8000 + Next :3000). One failing package fails the command.
7. Strictness: TS = alloy's tsconfig/base.json full-strict set unchanged (strict, noUncheckedIndexedAccess, exactOptionalPropertyTypes, noImplicitOverride, noFallthroughCasesInSwitch, noUncheckedSideEffectImports, verbatimModuleSyntax). Python = [tool.ty.rules] with every default-warn rule promoted to error.
8. Database: SQLAlchemy 2 + Alembic. Alembic scaffold/config lands in this issue; the first real migration lands with the first slice that needs a table.
9. Local run: pnpm dev. The docker compose file (Postgres, Redis, MinIO, workers) lands with the first slice that needs a service.
10. Test tiers: one fast tier now (pnpm test = Vitest + pytest, no services). A marked integration tier appears with the first test that touches Postgres/Redis.
11. Deferred verification: Playwright-for-Python on Python 3.14, checked when apps/worker lands.

Fixed constraints honoured, not re-argued: shadcn/ui over Tailwind, TanStack Query with mutations retry:false, no date library. Installing shadcn/Tailwind/TanStack Query is NOT part of this issue's scaffold; they land with the app-shell slice that needs them.

**claude** — 2026-08-14T05:21:14Z

PHASE 2 LANDED (2026-08-14). The alloy template is copied and renamed (step_by_step_api, @step-by-step/api-client), lockfiles regenerated, and all four checks pass green: pnpm check (format+lint+typecheck, both languages) and pnpm test (Vitest empty-suite pass + 2 pytest smoke tests), plus pnpm build and the full pnpm run ci chain, exit 0.

Beyond the straight copy:
- [tool.ty.rules] in the root pyproject.toml promotes all 23 rules ty 0.0.69 ships at default level warn to error (the list is in the file; revisit on ty upgrades via `ty explain rule`).
- SQLAlchemy 2.0.52 + Alembic added to apps/api; `alembic init` scaffold committed with env.py reading DATABASE_URL from the environment (alembic.ini carries no URL) and target_metadata=None until the first model lands.
- vp fmt now ignores .beaver/** — the tracker's files are the beaver CLI's, not the formatter's.
- Alloy's .gitignore replaced ours; the secrets entries (*.pem, *.key, secrets.*, .secrets/) were merged back in.
- AGENTS.md Checks section replaced wholesale; docs/ARCHITECTURE.md now records the layout, the typed API boundary, the dev proxy, the DB seam, strictness, and test tiers; README status updated.
- CI workflow (.github/workflows/ci.yml, three jobs: web, api, contract) came with the template — already in place for whenever a CI-capable remote appears.
