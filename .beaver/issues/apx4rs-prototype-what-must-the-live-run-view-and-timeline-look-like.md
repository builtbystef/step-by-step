---
id: apx4rs
title: 'Prototype: what must the live run view and timeline look like?'
state: todo
priority: medium
labels:
    - roadmap:idnzwf
    - session:prototype
depends_on:
    - px25yw
    - 4tjwpw
parent: idnzwf
created: 2026-08-10T03:34:26Z
updated: 2026-08-10T06:47:19Z
---

Live prototype session (prototype skill). The execution architecture is settled (px25yw): run states queued/running/waiting_for_human/succeeded/failed/cancelled with machine-readable failure reasons; step status, log lines, and screenshot-ready events arrive over SSE; screenshots are fetched as Artifacts by URL; a Batch's Runs execute sequentially. Answer with disposable UI:

- How does a single Run read while it executes: step progress, current step, logs, screenshots — and after it ends?
- How does the timeline render state transitions, including waiting_for_human intervals (entering/leaving takeover is 4tjwpw's ground — this view only shows that it happened)?
- What does a Batch's progress view look like: row-by-row status, the current Run, failed rows among succeeded ones?
- Where does drift visibility surface (a step that resolved on a low-ranked selector, wljln8) in the run detail?
- What does cancellation look like from this view?

Inputs: px25yw's note, ds8zyn's note (Step Result), docs/GLOSSARY.md. Coordinate with 4tjwpw (takeover UX) — this view hands off to it. The result feeds the backend + workers + live run spec.
