---
id: e181q4
title: 'Run output: the extracted-data table'
state: todo
priority: medium
depends_on:
    - 6ewr2p
    - oul652
parent: 9gea5p
created: 2026-08-14T07:44:33Z
updated: 2026-08-17T04:03:47Z
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
