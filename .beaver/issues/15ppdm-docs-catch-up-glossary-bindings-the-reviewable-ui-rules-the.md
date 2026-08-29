---
id: 15ppdm
title: 'Docs catch-up: glossary bindings, the reviewable UI rules, the execution shape'
state: done
assignee: agent
priority: low
labels:
    - maintenance
created: 2026-08-17T04:04:36Z
updated: 2026-08-29T06:17:28Z
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

## Notes

**agent** — 2026-08-29T06:17:27Z

Updated the three drifted docs against 54i6da, 9gea5p, and pc0t8s.

- GLOSSARY: a secret Variable binds to a Secret by id with the name cached for display (not by name, and not stored encrypted). Run status is queued → running ⇄ waiting_for_human → succeeded | failed | cancelled. Failure Reason is the closed set matching the Run store enum.
- CODING_STANDARDS: added the third reviewable-against-a-diff rule — one file per shared list (Run rows, Schedule rows). The hex and StatusChip/labels.ts rules were already there.
- ARCHITECTURE: added an Execution seam for the Worker model, the three transports (Redis, internal HTTP, VNC), and the ADR-0004 credentials boundary; named the lifecycle and Failure Reason set on the Run store. h9gene/f53mo0 and the executor/events slices had already landed, so this describes built reality.

No ADR or spec contradiction found. ADR 0002 (no automatic retries) and ADR 0004 (Workers never hold the master key) are restated, not reversed.
