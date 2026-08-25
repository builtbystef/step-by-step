---
id: tls69i
title: 'Artifacts: screenshots, trace chunks, downloads, and Run deletion'
state: done
assignee: agent
priority: medium
depends_on:
    - 6ewr2p
    - 1q7qp8
parent: 9gea5p
created: 2026-08-14T07:44:05Z
updated: 2026-08-25T20:18:49Z
---

## What to build

Everything a Run leaves behind. The `artifacts` table (run, step, kind screenshot | trace | download, object key, content type, size, index); Workers write objects to Garage directly and insert the rows themselves — bytes never pass through the backend — and announce each with an `artifact` event.

Screenshots are per Step and off by default: the Step's `screenshot` toggle (the document field d8ux2s's store holds) turns capture on for that Step, and a failing Step is always screenshotted regardless — diagnostics, not a preference. Playwright tracing runs for the whole Run, chunked with an `index`, each chunk openable in Trace Viewer; the secret-step holes and the takeover pause stay owned by the leak-prevention slice. Downloads are captured as produced and stored with their suggested filename.

Access and retention:

```
GET    /api/runs/{id}/artifacts/{artifactId}/download → 307 presigned URL
DELETE /api/runs/{id} → 204 (terminal only; purges rows and Garage objects)
                        409 code=run_active
```

No age- or size-based garbage collection in v1 — Artifacts live until their Run (or the account) is deleted.

## Acceptance criteria

- [ ] A Version with the screenshot toggle on for Step 2 only, run to success → exactly one screenshot Artifact, attached to Step 2.
- [ ] The same Version where Step 3 fails → two screenshots, the second belonging to the failed Step despite its toggle being off.
- [ ] A Run's trace chunk Artifacts carry a monotonically increasing `index` and each opens in Trace Viewer.
- [ ] A Step that downloads a file → a `download` Artifact with the suggested filename and content type, and the bytes in Garage match the fixture file.
- [ ] Each Artifact insert is announced by an `artifact` event carrying ids, never bytes.
- [ ] The download route checks ownership: the owner gets a 307 to a presigned URL that works and then expires; another user gets 404 and no URL is minted.
- [ ] `DELETE` on a `running` Run → 409 `run_active`; on a terminal Run → 204, and the Run's rows, Step Results, log lines, and Garage objects are all gone (verified by observing the object store).

## Notes

**claude** — 2026-08-17T04:03:58Z

Re-scope per ADR 0005: the download and delete routes' ownership check is the org Membership gate — another Organization's caller → 404; any member of the Run's Organization may download and delete. Screenshot precedence (mirrored on mdwnma): the always-screenshot-on-failure rule applies to automation failures only — a Step failed while the Run is in a waiting/human/verifying phase (takeover_timeout, takeover_abandoned) takes no failure screenshot; leak prevention outranks diagnostics, because the frame could hold an MFA code or a half-typed credential.

**agent** — 2026-08-25T20:03:14Z

Seams from the parent spec, no invention: (1) Worker executor at the existing Playwright fixture-page harness — screenshots, trace chunks, downloads, and artifact events (ids only) observed on the ResultStore protocol; Garage is not this tier. (2) Backend HTTP + Postgres + Garage — download 307/ownership/expiry and DELETE 409 run_active vs 204 purge, including object-store observation. Trace chunking in this slice is the whole-Run capture with a monotonic index; secret-step holes and takeover pause stay on mdwnma. Failure screenshots are automation failures only.

**agent** — 2026-08-25T20:18:49Z

Done. Artifacts for screenshots, trace chunks, downloads, and terminal Run deletion.

- artifacts table (kind screenshot|trace|download, object_key, content_type, size_bytes, index) with cascade from runs. Workers write bytes to Garage themselves; PostgresRunStore.add_artifact puts the object, inserts the row, and publishes an artifact event of ids only.
- Executor: screenshot when the Step toggle is on or the Step failed in automation; one Playwright trace chunk for the whole Run (monotonic index; secret-step holes stay on mdwnma); download Steps store suggested filename, content type, and fixture bytes.
- GET /api/runs/{id}/artifacts/{artifactId}/download → 307 presigned URL after the org Membership gate (foreign org → 404, no URL minted). DELETE /api/runs/{id} → 409 run_active while live, 204 on terminal after purging rows and Garage objects.
- GET /api/runs/{id} now lists Artifact records (filename is the object-key basename).
- Seams: Worker browser harness (screenshots, traces, downloads, events); HTTP+Postgres+Garage (download 307/expiry/ownership, DELETE purge). OpenAPI + generated client updated (downloadRunArtifact, deleteRun).
