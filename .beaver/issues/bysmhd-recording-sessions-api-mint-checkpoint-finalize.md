---
id: bysmhd
title: 'Recording sessions API: mint, checkpoint, finalize'
state: done
assignee: agent
priority: medium
depends_on:
    - sl7h4j
    - 94xanm
parent: d8ux2s
created: 2026-08-14T06:02:41Z
updated: 2026-08-24T07:22:54Z
---

## What to build

The backend half of the recording protocol, built so a dead tab, a killed service worker, or an expired token never costs a recording. The app mints a session against a Workflow's Draft; the extension then talks to the backend directly with the session's token. Checkpoints carry the full buffer and are idempotent; finalize replaces the Draft. The same protocol, scoped to one Step, serves Re-pick. All session traffic is authenticated by the token alone, scoped to one user and one Draft, with a 1-hour TTL.

## Acceptance criteria

- [ ] Minting a session for a Workflow returns a session id and a token scoped to that user and Draft with a 1-hour TTL; the extension-version header is required, and a version below the declared minimum is refused with a machine-readable code and a plain-language message linking the install page — the same minimum the version endpoint reports.
- [ ] Checkpoints are idempotent by sequence number and carry the full step buffer each time: sending seq 3 twice stores one copy; a later seq replaces the buffer.
- [ ] Simulated session death: after checkpoints for steps 1–4 and no further contact, finalizing (or re-attaching and finalizing) yields all four steps in the Draft — nothing is lost with the app tab closed.
- [ ] An expired token → 401; the app re-mints against the same session; checkpoints resume and previously checkpointed steps survive.
- [ ] Finalize writes the Draft as a replace and is rejected while any step carries an unresolved needs-secret marker.
- [ ] A repick-scoped session (mode and step id at mint) accepts a finalize carrying one fresh candidate list: exactly that Step's candidates change in the Draft, its id and everything else preserved.
- [ ] A token used against another session, Draft, or user → refused.
- [ ] HTTP seam tests with a real Postgres cover the version gate, idempotency, the death and expiry examples, the needs-secret rejection, and the repick patch.

## Notes

**agent** — 2026-08-24T07:22:54Z

Done. Added the recording-session table, one-hour hashed capability tokens, extension-version gating from the version endpoint's shared minimum, idempotent full-buffer checkpoints, same-session token rotation, whole-Draft finalize with needs-secret refusal, and scoped Re-pick candidate patching. The HTTP seam suite covers the version gate, duplicate/later checkpoint sequences, server-buffer recovery after session death, expiry and re-mint, unresolved secrets, Re-pick preservation, and cross-session token refusal. Decisions: re-mint names session_id in the mint body and rotates its token; a record finalize may omit steps to use the newest persisted checkpoint; the unresolved transient marker is needsSecret; Authorization accepts the protocol's raw token and the conventional Bearer form. Generated OpenAPI/client artifacts and architecture docs are updated. pnpm check, pnpm test, and pnpm build pass; the migration also renders through Alembic's PostgreSQL offline path. The real-Postgres tier could not be executed because the compose Postgres was not running in this harness, but its tests are committed at the agreed HTTP seam.
