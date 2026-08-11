---
id: kvz5sv
title: 'Spec: execution, workers, and the live run view'
state: todo
labels:
    - roadmap:idnzwf
    - session:spec
depends_on:
    - px25yw
    - 1ar6xu
    - 4tjwpw
    - apx4rs
parent: idnzwf
created: 2026-08-11T19:45:28Z
updated: 2026-08-11T19:45:28Z
---

Write the spec for the execution area (session:spec). The area's nodes: execution architecture — isolation, queue semantics, streaming (px25yw, with ADR 0002); mid-run browser takeover research (1ar6xu); takeover UX prototype (4tjwpw); live run view and timeline prototype (apx4rs).

Read those nodes' notes and linked artifacts (this area's only). Interview to close remaining gaps (grill-me), confirm with the user, then invoke the create-specification skill. Publish the spec issue with a blocking edge back to each node it covers.

Boundaries already fixed by neighbouring specs:

- The recording/editing/storage spec (d8ux2s) owns the Step document, the Draft/Version model, and the selector resolution module contract (`resolve(page, target, deadline)`, ordered fallback, ambiguity rejected, timeout as the retry budget). This spec consumes them; it does not redefine them.
- The secrets spec (000gz2) owns the Secret vault and Auth State storage. This spec consumes their injection and write-back contract.
- Accounts and authentication are spec ufnuvx.

This spec owns: Run lifecycle and statuses, the Redis queue and Worker pool, per-Run browser isolation, Step Result writing, Artifact production and storage, the SSE event stream, the scheduler loop, Batch execution, cancellation, takeover (enter, control, hand back, timeout), and the live run and batch views.
