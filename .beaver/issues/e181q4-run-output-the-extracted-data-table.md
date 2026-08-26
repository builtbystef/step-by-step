---
id: e181q4
title: 'Run output: the extracted-data table'
state: done
assignee: agent
priority: medium
depends_on:
    - 6ewr2p
    - oul652
parent: 9gea5p
created: 2026-08-14T07:44:33Z
updated: 2026-08-26T15:51:21Z
---

## What to build

The Run's product as something usable. Output is assembled on read from Step Results' extracted values — nothing is stored twice:

```
GET /api/runs/{id}/output?format=json|csv → 200 assembled output
```

And the cockpit gains its Output tab: the assembled object rendered as a table, with Download JSON and Download CSV.

## Acceptance criteria

- [ ] A Run with a list-mode extract of 24 records → the CSV has 24 data rows with the field names as the header row; the JSON is the same records.
- [ ] A Run with two extract Steps → the output combines both under their Step's output names.
- [ ] A Run with no extract Steps → an empty output, and the tab says so rather than rendering an empty table frame.
- [ ] A failed Run's output contains what was extracted before the failure.
- [ ] The Output tab renders the records as a table and both download buttons deliver the endpoint's formats.
- [ ] Ownership holds: another user's Run id → 404.

## Notes

**claude** — 2026-08-17T04:03:47Z

Re-scope per ADR 0005: ownership is the org Membership gate — another Organization's Run id → 404; any member of the Run's Organization reads the output.

**agent** — 2026-08-26T14:32:41Z

Seams: parent spec Seam 1 (HTTP against FastAPI + real Postgres) for assembly, formats, failed-run partial output, and org Membership 404. Frontend seam matching oul652: pure functions for empty-vs-table and download URLs, read back with no DOM. Output is assembled on read from Step Results keyed by extract outputName; a single list-mode extract unwraps to the records so CSV headers are field names.

**agent** — 2026-08-26T15:51:21Z

Done. GET /api/runs/{id}/output assembles extract Step Results on read (nothing stored twice) as JSON or CSV. The cockpit Output tab renders that payload as a table, or the empty sentence when there is nothing to show.

Seams: parent spec Seam 1 (HTTP + real Postgres) for assembly, formats, failed-run partial output, and org Membership 404. Frontend seam matching oul652: outputTable / EMPTY_OUTPUT / outputDownloadHref, read back with no DOM.

What landed
- A single list-mode extract unwraps to the records so CSV headers are the field names (24 rows in the worked example).
- Two extract Steps combine under their outputName keys.
- No extract Steps → {} / empty CSV; the tab says "This Run extracted no data." and draws no table frame.
- A failed Run still returns what was extracted before the failure.
- Another Organization's Run id → 404 run_not_found; any member of the Run's Organization reads the output.
- Download JSON / Download CSV point at ?format=json|csv.

Decisions
- Only a lone list of records unwraps; a single scalar stays keyed by outputName, matching the "combines both under their names" shape.
- The tab renders the endpoint's assembled object, it does not re-assemble from Step Results on the client.
- Empty output hides the download buttons as well as the table frame.

pnpm check (vp check + ruff/ty) and the fast test suite pass. Integration: tests/integration/test_run_output.py (6) green against the compose sockets.
