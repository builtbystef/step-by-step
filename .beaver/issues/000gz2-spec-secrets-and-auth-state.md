---
id: 000gz2
title: 'Spec: secrets and auth state'
state: todo
labels:
    - roadmap:idnzwf
    - session:spec
depends_on:
    - 7o0nmx
    - u7nkwh
parent: idnzwf
created: 2026-08-11T19:45:17Z
updated: 2026-08-11T19:45:17Z
---

Write the spec for the secrets + auth state area (session:spec). The area's nodes: secrets and auth state storage/scoping/injection (7o0nmx, with ADR 0003), and reuse of Chrome-recorded auth state in a Playwright browser (u7nkwh).

Read those nodes' notes and linked artifacts (this area's only). Interview to close remaining gaps (grill-me), confirm with the user, then invoke the create-specification skill. Publish the spec issue with a blocking edge back to each node it covers.

Boundaries already fixed by neighbouring specs:

- The recording/editing/storage spec (d8ux2s) binds a `type` Step to a secret Variable by name only. This spec owns the Secret vault itself: storage, envelope encryption under the env-supplied master key (ADR 0003), vault UX, rotation, and the per-domain opt-in Auth State capture prompt at recording save.
- Injection into a Run's browser and write-back from a Worker are this spec's contract; the execution spec consumes it.

Out of scope, already settled on the root: cloud KMS integration, per-workflow secret values, per-domain locks or freshness stamps for Auth State write-back, suppressing screenshots on secret-referencing steps, silent Auth State export from the extension.
