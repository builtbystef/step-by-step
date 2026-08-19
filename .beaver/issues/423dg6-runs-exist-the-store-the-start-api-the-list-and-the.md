---
id: 423dg6
title: 'Runs exist: the store, the start API, the list, and the dispatch queue'
state: todo
priority: high
depends_on:
    - f53mo0
    - g795ji
parent: 9gea5p
created: 2026-08-14T07:41:05Z
updated: 2026-08-19T20:02:05Z
---

## What to build

The Run as data, and the way Runs reach the queue. Four tables: `runs` (the full column set — trigger, status, failure_reason/detail, non-secret variables, timeout, worker fields, heartbeat, control-request stamps, takeover fields, queued/started/ended timestamps, automation_ms, and the test-run pair draft_snapshot/is_test with a null version), `step_results` (one row per Step the Run reached, status passed | failed | skipped, matched_candidate_rank, completed_by_human, error, diagnostics, extracted_value), `run_control_intervals` (kind automation | waiting | human | verifying — this table IS the timeline), and `run_log_lines`. The lifecycle is queued → running ⇄ waiting_for_human → succeeded | failed | cancelled, with the closed v1 `failure_reason` set: step_failed, auth_challenge, takeover_timeout, takeover_abandoned, run_timeout, worker_lost, missing_secret, startup_failed.

The user-facing surface:

```
POST   /api/workflows/{id}/runs  {variables, test?: bool} → 201 {run_id}
GET    /api/runs?workflow_id=&status=&limit=&cursor=      → 200 [RunSummary]
GET    /api/runs/{id}  → 200 {run, step_results, control_intervals, artifacts, batch_row?}
POST   /api/runs/{id}/cancel     → 202
```

Starting a Run stores the supplied non-secret Variable values (secret Variables carry the binding, never a value), snapshots the Draft when `test` is true, and enqueues the Run id with one `LPUSH` onto the single Redis dispatch list. Redis is never asked to be reliable — Postgres is the truth. Cancelling a `queued` Run flips the row to `cancelled` at once. Cancellation of running and waiting Runs arrives with the control slice; execution itself with the executor slice.

## Acceptance criteria

- [ ] Start a Run while no Worker consumes → 201, status `queued`, and the Run id is on the Redis list exactly once.
- [ ] A test Run (`test: true`) stores the Draft snapshot, has a null Version id, and `trigger` = `test`; a normal Run records the latest published Version and `trigger` = `manual`.
- [ ] The stored `variables` of a Run with a secret Variable contain the non-secret values and nothing for the secret one.
- [ ] Cancel a `queued` Run → status `cancelled` at once.
- [ ] `GET /api/runs?workflow_id=X&status=failed` returns only that Workflow's failed Runs; keyset paging over 25 seeded Runs with page size 10 yields 25 distinct ids in order.
- [ ] The detail response carries the Run, its Step Results in position order, its control intervals, and its artifacts in one payload.
- [ ] Every route is scoped to the calling user: another user's Run id → 404.
- [ ] Starting a Run of a Workflow with no published Version is rejected with a clear error (test Runs excepted).

## Notes

**claude** — 2026-08-17T04:03:37Z

Re-scope per ADR 0005 (see the note on 9gea5p): runs gains org_id (FK organizations, cascade) and a nullable starter user_id (set for manual/test starts, null for schedule/batch); every route scopes to the active Organization via the shared X-Organization gate — 'another user's Run id → 404' reads 'another Organization's Run id → 404', and any member of the Run's Organization sees it. Land the attention-index ground here: a partial index on (org_id, takeover_deadline_at) over non-terminal statuses — fkgat7 later asserts its plan. Also settle missing_secret precedence: the 409 on POST .../runs is a best-effort pre-check for request-time starts; the authoritative check is the credentials fetch at claim (clxd1b) — schedule/batch starts have no request to refuse, and a Run whose Secret disappears between start and claim ends failed/missing_secret.

**claude** — 2026-08-19T20:02:05Z

From 5rkj33 (the Workflows list): the frontend already renders a `no_published_version` refusal as the shared sentence `COPY.noPublishedVersion` ("Publish a Version before this Workflow can run."), and `app/(shell)/workflows/messages.ts` maps that code to it. When this slice builds POST /api/workflows/{id}/runs, the refusal for a Workflow with no published Version should carry exactly that code, so the mapping and the disabled Run/New batch/New schedule actions line up with the route.
