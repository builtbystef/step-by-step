---
id: fpzupm
title: Schedules gain a value set, a name, and a derived state
state: todo
priority: high
depends_on:
    - g461z0
parent: nno9gj
created: 2026-08-14T19:51:01Z
updated: 2026-08-14T19:51:01Z
---

## What to build

A Schedule that owns its Variable values, so two Schedules of one Workflow can do different work. `schedules` gains `name` (nullable — a blank name shows the recurrence sentence in its place, on the surfaces other slices build) and `variables` JSONB holding **non-secret values only**, the same rule as a Run's and a Batch row's values: a secret Variable carries the binding, never the value. A fired Run copies the Schedule's values.

The CRUD contract grows values and a name, and refuses to create a broken unattended job:

```
POST   /api/workflows/{id}/schedules  {cron, timezone, enabled, variables, name?}
         → 201
           400 code=invalid_cron | code=invalid_timezone
           400 code=missing_variable_values {variable_names}
           409 code=no_published_version
PATCH  /api/schedules/{id}  {cron?, timezone?, enabled?, variables?, name?} → 200 (the same 400s)
```

A Schedule's state is **derived on read, never stored**: `paused` when `enabled` is false; otherwise `needs_values` when the Workflow's latest published Version declares a non-secret Variable whose name is absent from `variables`; otherwise `active`. Deriving it means publishing a Version cannot forget to set a flag, and a flag can never go stale against the document it describes.

## Acceptance criteria

- [ ] `POST` with a value absent for a declared non-secret Variable → 400 `missing_variable_values` naming it; with every non-secret Variable covered → 201. A secret Variable neither requires nor accepts a value.
- [ ] `POST` for a Workflow with no published Version → 409 `no_published_version`.
- [ ] Publish a Version declaring a new non-secret Variable `region` → the Schedule reads `state: needs_values` with `missing_variable_names: ["region"]`, with no write to the Schedule's row; `PATCH` supplying the value → `active` again.
- [ ] `enabled: false` → `paused`, regardless of value coverage, and distinct from `needs_values`.
- [ ] The stored `variables` of a Schedule of a Workflow with a secret Variable contain nothing for the secret one.
- [ ] A Run fired by the scheduler carries the Schedule's `variables` as they are at fire time.
- [ ] `name` is stored, patchable, and nullable.
