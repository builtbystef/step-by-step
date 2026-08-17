---
id: 15ppdm
title: 'Docs catch-up: glossary bindings, the reviewable UI rules, the execution shape'
state: todo
priority: low
labels:
    - maintenance
created: 2026-08-17T04:04:36Z
updated: 2026-08-17T04:04:36Z
---

## What to update

Three docs drifted behind the specs; reviews and fresh sessions read them as authoritative.

- `docs/GLOSSARY.md`: a secret Variable binds to a Secret **by id with the name cached for display** (54i6da) — not by name. Add the Run lifecycle vocabulary (`queued → running ⇄ waiting_for_human → succeeded | failed | cancelled`) and the closed `failure_reason` set, which no doc currently defines.
- `docs/CODING_STANDARDS.md`: promote the rules the specs explicitly frame as reviewable against a diff — no raw hex outside the token definitions; no lifecycle state rendered except through StatusChip; one file per shared list (Run rows, Schedule rows); state wording only through `lib/labels.ts` (pc0t8s, d8ux2s).
- `docs/ARCHITECTURE.md`: the execution shape (Worker model, transports, the vault's ADR-0004 boundary) lives only in issue bodies. h9gene and f53mo0 own their own sections as they land; sweep the remainder in once the executor/events slices exist.

## Acceptance criteria

- [ ] The three updates above are in place and consistent with the specs they cite.
- [ ] Nothing in the updated docs contradicts an ADR or a spec issue.

Best run after the shell and executor waves so the architecture section describes built reality, not plans.
