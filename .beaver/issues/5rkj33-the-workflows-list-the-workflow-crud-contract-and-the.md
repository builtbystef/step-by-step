---
id: 5rkj33
title: The Workflows list, the Workflow CRUD contract, and the Workflow page
state: done
assignee: claude
priority: medium
depends_on:
    - hat4cf
    - sl7h4j
    - g795ji
parent: pc0t8s
created: 2026-08-14T05:55:09Z
updated: 2026-08-19T20:03:27Z
---

## What to build

The screen a user lands on, and the routes no other spec defines. List, create, rename, duplicate, and delete for Workflows — additive to the recording spec, which keeps every Draft and Version behavior it owns — plus the Workflow detail page: a header with the name, the draft-state chip, and a Run action, over four linkable tabs (Editor default, Runs, Schedules, Batches; the tab contents beyond Editor arrive with later slices). The list's Run-derived and Schedule-derived columns, the delete guard against a live Run, and the cascade over Runs and Schedules belong to a follow-up slice, once those objects exist — this slice computes what the Workflow/Draft/Version ground provides.

## Acceptance criteria

- [ ] The list endpoint returns Workflow summaries (id, name, created and last-activity times, draft state, published version when one exists, schedule and run fields as the data allows) and supports `q`, three sorts, and keyset cursor paging: sorted by name with page size 10 over 25 Workflows, paging to exhaustion yields 25 distinct ids in name order with none seen twice, stable while rows change underneath.
- [ ] `q=acme` matches names case-insensitively; sort defaults to activity; a never-run Workflow orders by its own updated time.
- [ ] Create with a name → 201; rename → 200; duplicate → 201 where every Step id differs from the source, order and payloads match, and the copy's draft state is never-published.
- [ ] Delete → 204 and the Workflow's Drafts and Versions are gone; the confirm dialog names what goes with it and is plain confirm, not type-to-confirm — that ceremony stays reserved for account deletion.
- [ ] A Workflow with no published Version reports draft state never-published with no published version, and starting it is refused with a machine-readable no-published-version code, rendered everywhere as the one shared sentence.
- [ ] The row: name as primary; a meta line with the last Run's status chip and relative time (or "never run") and the schedule indicator when data exists; the draft-state badge on the right (neutral never-published, amber unpublished changes, green in-sync-with-version); hover actions — inline Run, and an overflow with New batch, New schedule, Duplicate, Rename, Delete. Run, New batch, and New schedule are disabled behind the shared sentence while never-published; row click opens the editor tab.
- [ ] The search box and sort control render only at 40 rows or more; the endpoint always supports both.
- [ ] New workflow is a primary button opening a name-only dialog and landing on the empty Editor tab.
- [ ] The Workflow page header shows name, draft-state chip, a Run action available from every tab, and an overflow repeating the row actions; the four tabs are each their own URL, the bare Workflow path redirects to the editor tab, and the back button walks tabs.
- [ ] HTTP seam tests with a real Postgres cover the paging, search, sort, duplicate, delete, and never-published examples.

## Notes

**claude** — 2026-08-19T20:02:32Z

Done. The Workflows list, the CRUD contract around the document, and the Workflow page with its four tabs.

**Seams** (as the spec's Testing Decisions name them): the backend HTTP API against a real Postgres, and pure frontend functions read back with no DOM. No component or DOM tests — there is still no rendering stack in this repo, and the spec ruled that trade out.

**What landed**

- `workflows/catalog.py` — a module beside `routes.py`, because the document store owns Drafts and Versions and this contract is the app shell's ground. `GET /api/workflows` (q, three sorts, keyset cursor paging), `GET /api/workflows/{id}`, `PATCH`, `POST /{id}/duplicate`, `DELETE`. All five reach the Workflow through one org-scoped lookup, so another Organization's is 404 on every one.
- `workflows/models.py` — `workflows.updated_at`, migration `a4f7c2b19e83`. Existing rows take their creation time.
- `workflows/document.py` — `standing()` (the tri-state rule, with the document comparison taken out of it) and `with_fresh_step_ids()`.
- `workflows/routes.py` — its `WorkflowSummary` is now `WorkflowRecord`; the name belongs to the list row the spec pinned.
- 23 HTTP seam tests in `tests/integration/test_workflow_catalog.py`, covering the paging, search, sort, duplicate, delete, and never-published worked examples.
- `apps/web/app/(shell)/workflows/` — the list, the row, the two dialogs, and `[id]/` with the header, the four tabs, the bare-path redirect, and a placeholder per tab. The decisions are in `list.ts`, `actions.ts`, `draft-state.ts`, `messages.ts`, and `[id]/tabs.ts`, each read back by a test. `lib/relative-time.ts` is new; shadcn's `Dialog` was generated in (nothing else it writes was kept).

**Decisions**

- **The list answers `{items, next_cursor}` rather than a bare array.** Keyset paging needs the position to come from the server: the cursor is base64 `(sort, key, id)`, and it is refused in any order but the one it was cut from, because the same token names a different place in a different order. `next_cursor` is absent on the last page — an empty final page would be one request too many.
- **The draft state is compared in the database and worded in Python.** A list of a hundred rows would otherwise drag a hundred Draft documents and a hundred Version documents across to compare them; `standing()` keeps the three words in the one place `draft_state()` already had them.
- **`last_activity_at` is `GREATEST(workflows.updated_at, workflow_drafts.updated_at)`.** Renaming touches the one and editing the document touches the other, and both are things that happened to the Workflow. `0746dg` replaces it with the latest Run's time, falling back to this pair.
- **`GET /api/workflows/{id}` was added**, which the spec's route table does not list. The Workflow page's header renders the name and the draft-state chip, and opened by its address rather than by a click it has no row to have carried them. It answers the same query the list does, so a reload cannot disagree with the row.
- **Sorts are a closed set of three.** Each is a keyset the cursor is built on; a fourth would need its index first. An unknown sort is a 422.
- **A duplicate is named `<name> (copy)`, trimmed from the left** so the suffix survives a name at the column limit, and it copies the Draft alone. Copying Versions would deliver an automation nobody has looked at that is ready to act on a real website.
- **Housekeeping is not disabled by `never-published`.** Run, New batch, and New schedule are, behind the one shared sentence; Duplicate, Rename, and Delete are not, because a Workflow nobody published is exactly the one somebody wants to throw away.
- **Page size is the forty-row threshold.** That is what lets the first page decide whether the search box and the sort control render, with no count query: a full page means at least forty Workflows exist. The controls stay while a search is on, however few rows it left.

**Deferred, and where to**

- **The `409 no_published_version` refusal itself is `423dg6`'s**, which owns `POST /api/workflows/{id}/runs`; there is no Run table yet, and a route that could only ever refuse is not a route. What this slice does own is already here: the summary reports `never-published` with no `published_version`, the three actions are disabled behind `COPY.noPublishedVersion`, and `messages.ts` renders that code as the same sentence. A note on `423dg6` pins the code.
- **The row's last-Run chip, the schedule indicator, the activity sort following real Runs, the `409 run_active` delete guard, and the cascade over Schedules/Batches/Runs** are `0746dg`'s, as the issue body says. Every row currently reads "never run", which is true of every Workflow there can be.
- **The two-step first-run panel** on an empty Workflows screen is `20k5ft`'s; until it lands the screen shows an `EmptyState`.

**For a reviewer**

- Tenancy is asserted per route: another Organization cannot list, read, rename, duplicate, or delete a Workflow, and gets 404 rather than 403 on each.
- The paging test changes a row underneath on every page and still gets 25 distinct ids in name order — that is the keyset claim, tested rather than asserted in a comment.
- `docs/ARCHITECTURE.md`, `apps/api/openapi.json`, and the generated client are updated.
