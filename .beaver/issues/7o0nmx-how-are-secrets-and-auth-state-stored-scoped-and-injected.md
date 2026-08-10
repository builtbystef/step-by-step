---
id: 7o0nmx
title: How are secrets and auth state stored, scoped, and injected without leaking?
state: todo
priority: medium
labels:
    - roadmap:idnzwf
    - session:grill
depends_on:
    - 8iuuh8
    - u7nkwh
parent: idnzwf
created: 2026-08-08T07:08:04Z
updated: 2026-08-08T07:08:04Z
---

One live interview (grill-me). With tenancy (8iuuh8) and auth-state transfer realities (u7nkwh) known, decide:

- What v1 stores: site credentials, exported session state, both? Encryption at rest (KMS? libsodium? app-level key) and key management for the chosen deployment shape.
- Scoping: secrets per workflow, per site, per user?
- Injection at run time: how a typed-password step references a secret, and how values are kept out of logs, traces, screenshots, and step payloads.
- Lifecycle: rotation, revocation, what happens on takeover when the user types a password into the worker browser.
