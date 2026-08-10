---
id: b9ur3b
title: 'Spec: accounts and authentication'
state: todo
labels:
    - roadmap:idnzwf
    - session:spec
depends_on:
    - 8iuuh8
    - imtsfx
parent: idnzwf
created: 2026-08-10T23:47:49Z
updated: 2026-08-10T23:47:49Z
---

The accounts area is settled; write its spec (session:spec — read the notes and linked artifacts of this area's closed nodes, interview to close remaining gaps, confirm, then invoke the create-specification skill).

Area nodes: 8iuuh8 (tenancy: multi-tenant personal accounts, self-hosted, ADR 0001) and imtsfx (sign-in, provisioning, Instance Admin, sessions, password reset/recovery, disable and delete semantics).

The spec covers: registration and first-user-becomes-admin bootstrap; the open-signup instance setting; email/password sign-in; the server-side session model (opaque ID, httpOnly SameSite cookie, sliding 30-day expiry); temp passwords and forced change; admin CLI recovery commands; disabling a user (sessions, Schedules, queued vs. running Runs); hard-cascade account deletion (self and admin, last-admin rule, cancellation of in-flight Runs, purge across Postgres and MinIO).

Boundary: the extension's recording-scoped credential belongs to n52g83's ground, not this spec.
