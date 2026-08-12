---
id: smpcpi
title: 'Spec: the app shell, the lists, and the visual language'
state: todo
priority: high
labels:
    - roadmap:idnzwf
    - session:spec
depends_on:
    - dm4cff
    - 7mfxzj
parent: idnzwf
created: 2026-08-12T04:07:31Z
updated: 2026-08-12T04:07:31Z
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
