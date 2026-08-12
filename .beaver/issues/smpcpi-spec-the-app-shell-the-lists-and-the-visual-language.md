---
id: smpcpi
title: 'Spec: the app shell, the lists, and the visual language'
state: done
assignee: claude
priority: high
labels:
    - roadmap:idnzwf
    - session:spec
depends_on:
    - dm4cff
    - 7mfxzj
parent: idnzwf
created: 2026-08-12T04:07:31Z
updated: 2026-08-12T05:16:37Z
---

Write the spec for the frame every other surface sits inside. The five published specs (`ufnuvx`, `d8ux2s`, `54i6da`, `9gea5p`, `nno9gj`) each describe one deep surface and assume this frame without describing it; this spec is that frame, and nothing else. Do not re-decide anything those five settled.

Read the notes and artifacts of the area's closed nodes:

- `dm4cff` — the map. The sidebar's three primary destinations (Workflows, Runs, Schedules) plus Settings with its five sections; no dashboard, with the attention band and the Runs badge in its place; Runs history as one component used globally and filtered on the Workflow; the Workflow page's four tabs; the Workflows list row, its actions and its forty-row behavior; the three auth screens outside the shell; the empty and first-run states; and the extension status pill.
- `7mfxzj` — what those screens look like, and the visual language they establish: the type scale, spacing, status colors, and the named primitives the five specs already use in prose (status chip, amber callout, red banner, locked column, drift badge, hatched occurrence, expand-in-place row, sticky footer). Its prototype branch is the evidence.

What this spec must settle that its inputs leave open:

1. **The attention endpoint.** `dm4cff` added `GET /api/attention` as an additive touch to `9gea5p`, because v1 SSE is per-Run and nothing can feed a shell-level indicator. Settle its exact shape, its polling interval, and what it costs on an instance with a large Run history.
2. **Route table and guards.** Which routes are outside the shell, what an unauthenticated request to a shell route does, and how `must_change_password` (which 403s every other authenticated endpoint) is enforced in the frontend rather than discovered as a wall of errors.
3. **The shared list component.** Runs global vs. Runs-on-a-Workflow are one component; so are the all-Schedules table and the Workflow's Schedules tab (`nno9gj`). Name the contract that makes "filtered by workflow_id" a parameter and not a fork.
4. **Where the primitives live** so that the first implementation session inherits the vocabulary instead of inventing one.

Interview to close the remaining gaps, confirm with the user, then invoke the `create-specification` skill. Publish the spec issue with a blocking edge back to `dm4cff` and `7mfxzj`.

## Notes

**claude** — 2026-08-12T05:16:37Z

ANSWER — the spec for the app-shell area is published as `pc0t8s`, "The app shell, the lists, and the visual language", with blocking edges back to `dm4cff` and `7mfxzj`. It covers the frame the five earlier specs each assumed and none described, and it re-decides nothing they settled.

WHAT THE SPEC SETTLED THAT ITS INPUTS LEFT OPEN — the four gaps this node named, plus three the drafting exposed. Every one was put to the user and approved; the eighth was corrected by the user mid-session and the correction is recorded below.

1. THE ATTENTION ENDPOINT. `GET /api/attention` -> {waiting: [{run_id, workflow_id, workflow_name, deadline_at}] capped at 5 and ordered soonest-first, waiting_count (the true total), running_count, queued_count}. Polled every 10 s only while document.visibilityState is 'visible', refetched on focus, never mounted outside the shell, and invalidated (not re-polled) after any action that can change it and on an SSE transition into or out of waiting_for_human. The countdown ticks client-side from deadline_at, so the 10 s cadence never coarsens the timer, and when it hits zero the band says the deadline passed rather than asserting an outcome — the reaper in 9gea5p is what flips the Run to takeover_timeout. COST: a partial index runs_attention on (user_id, deadline_at) WHERE status IN ('queued','running','waiting_for_human'). An instance with 50k terminal Runs and 3 non-terminal ones scans 3 index entries, and one round trip serves the band and the badge together. The nav badge is running + queued + waiting, amber when waiting > 0.

2. ROUTE TABLE AND GUARDS. Three routes outside the shell (/signin, /signup, /set-password); the full inside-the-shell table is in the spec. The guard is ONE PURE FUNCTION, resolveGate(me, pathname) -> {kind:'render'} | {kind:'redirect', to}, with eight ordered rules, called by the shell layout after it resolves GET /api/auth/me once. must_change_password is therefore a single redirect to /set-password instead of a wall of 403s, and /set-password is unreachable once the flag clears. A global fetch wrapper over every /api/* call maps 401 -> /signin?next=... and 403 code=must_change_password -> /set-password, so a tab left open across a session expiry or an admin reset recovers. 'next' is honored only when it starts with a single slash and names no auth route.

3. THE SHARED LIST CONTRACT. RunsList and SchedulesList each exist exactly once, and workflowId is their ONLY prop. It changes exactly three things: it adds ?workflow_id=, it hides the Workflow column, and it swaps the empty state for the Workflow's own call to action. The reviewable form of the rule: if a second file renders Run rows or Schedule rows, the rule is broken. Both sit on one useCursorList hook wrapping useInfiniteQuery, whose key [path, filters] is also what a mutation invalidates.

4. WHERE THE PRIMITIVES LIVE. Three layers: components/ui/* is shadcn, generated and never hand-edited; components/primitives/* holds the eleven named primitives, one file each, and each is the only place its idea is rendered; app/globals.css carries the semantic ramp beside shadcn's tokens. Plus lib/labels.ts as the single source of every state's wording (waiting_for_human reads 'needs you' everywhere, and no screen phrases a status itself) and lib/copy.ts for the sentences that must be identical across screens. Two rules a review can check against a diff: no raw hex outside the token file, and no lifecycle state rendered except through StatusChip. Because the user chose to keep the visual language in the spec rather than in a docs/ file, pc0t8s is its only durable record — the prototype branch is disposable.

GAPS THE DRAFTING EXPOSED, each settled in the spec:

5. WORKFLOW CRUD HAD NO OWNER. d8ux2s specifies Draft and Version behavior but lists only the recording-session routes, so no published spec defined the routes this screen's rows and actions call. The spec defines them, additive to d8ux2s: GET /api/workflows?q=&sort=activity|name|created&limit=&cursor= -> [WorkflowSummary], POST /api/workflows {name}, PATCH (rename), DELETE (cascade, 409 run_active while a Run is live), POST /api/workflows/{id}/duplicate. Search and sort are server-side over a keyset cursor, because the forty-row rule is a UI threshold and not a ceiling. WorkflowSummary names draft_state as the three states of d8ux2s's Draft chip.

6. THE SIGNUP PAGE HAD NO UNAUTHENTICATED SOURCE for which of its three states to render — ufnuvx puts open_signup behind an admin route. New, additive to ufnuvx: GET /api/instance -> {signup_state: 'bootstrap'|'open'|'closed'}, unauthenticated. Also additive to ufnuvx: the must-change 403 carries code=must_change_password, because the fetch wrapper has to tell it from any other 403.

7. SMALLER CALLS. Batch progress is a flat /batches/[id], because a Run's batch_row backlink carries only the batch id — refusing a global Batches index (nno9gj) does not refuse a batch detail route. The inline Run on a list row opens nno9gj's one-row value grid when the Workflow declares Variables, and starts immediately when it does not. Delete names its cascade in a confirm dialog rather than type-to-confirm, which stays reserved for account deletion. A filter matching nothing is a line inside the table, never the EmptyState — 'you have none' and 'none match' have different next actions. The extension handshake treats silence for 1500 ms as not-connected and re-probes on focus.

8. TANSTACK QUERY — A CORRECTION MADE IN SESSION. The draft first rejected a data-fetching library, arguing partly from ADR 0002. The user challenged it and the argument did not hold: ADR 0002 forbids automatic retries of a RUN, which is not idempotent and acts on a real website; refetching our own read endpoints is a different hazard entirely. The 'few caches' premise also undercounted — /auth/me deduped across the shell, visibility-aware attention polling, four cursor lists, invalidation after mutations, and SSE-driven invalidation are a precise description of the library's job. The spec now takes TanStack Query, with TWO MANDATED DEFAULTS: mutations: {retry: false}, because a retried POST /api/workflows/{id}/runs or /api/schedules/{id}/run-now is a second Run acting on a real site — the hazard nno9gj's 'two copies never act at once' invariant exists to prevent — and an explicit per-key query retry and staleTime rather than the library's. That is the one place ADR 0002's spirit does carry. Recorded on ymz3md as a stack fact, the same way 7mfxzj recorded shadcn/ui.

SEAMS, agreed with the user — two. Seam 1 is the backend HTTP API against a real Postgres, the same seam all five published specs use; its worked examples include an EXPLAIN assertion that the attention query touches 3 rows on an instance with 50k terminal Runs, so the cost claim is tested rather than hoped. Seam 2 is resolveGate as a pure function with a ten-row redirect matrix — the one piece of real frontend logic this spec adds, testable with no browser and no DOM. No component or DOM tests: the primitives are presentational, the lists' one behavioral rule is three lines of conditional rendering, and a rendering stack does not exist in this codebase yet.

NO GLOSSARY ADDITIONS — every domain concept is already defined, and the primitives are UI vocabulary. NO ADR — the attention band is cheap to reverse, and the stack facts belong to ymz3md.

CONSEQUENCE FOR THE ROADMAP: every decision node under idnzwf is now closed and all five-plus-one areas are specced. Only the Frontier remains, so the next advance-plan session's job is the Frontier itself.
