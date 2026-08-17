---
id: tls69i
title: 'Artifacts: screenshots, trace chunks, downloads, and Run deletion'
state: todo
priority: medium
depends_on:
    - 6ewr2p
    - 1q7qp8
parent: 9gea5p
created: 2026-08-14T07:44:05Z
updated: 2026-08-14T07:44:05Z
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
