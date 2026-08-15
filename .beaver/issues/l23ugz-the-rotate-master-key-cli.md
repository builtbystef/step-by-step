---
id: l23ugz
title: The rotate-master-key CLI
state: todo
priority: low
depends_on:
    - 3679bv
    - gl1cnk
parent: 54i6da
created: 2026-08-14T06:16:35Z
updated: 2026-08-15T04:15:05Z
---

## What to build

One command in the backend container: `rotate-master-key` re-wraps every sealed row's data key — Secrets, Auth States, and the Personal Overrides of both — from `STEPBYSTEP_MASTER_KEY` to `STEPBYSTEP_NEW_MASTER_KEY`, so a leaked key is recoverable without dumping and reloading the database. Record plaintexts are never decrypted or rewritten — only the data keys are re-sealed. Per record it tries the current key first, then the new one, so a re-run after a partial failure completes rather than corrupts. It prints re-wrapped and already-rotated counts. The operator swaps the environment variables and restarts the backend afterwards.

## Acceptance criteria

- [ ] Rotation over N mixed records (Secrets, Auth States, and Personal Overrides of both) → every record opens under the new key, none under the old, plaintexts byte-identical.
- [ ] Re-run against an already-rotated table → zero re-wrapped, N already-rotated, no corruption.
- [ ] A rotation interrupted partway completes on re-run, with every record readable under the new key afterwards.
- [ ] The command refuses to run when `STEPBYSTEP_NEW_MASTER_KEY` is absent or malformed, with the same validation the boot gate applies.

## Notes

**claude** — 2026-08-15T04:15:05Z

The account recovery CLI (8wxso0) it stood beside is cancelled under ADR 0005 — this slice now lands the backend container's CLI entry point itself; the rotation behavior is unchanged.
