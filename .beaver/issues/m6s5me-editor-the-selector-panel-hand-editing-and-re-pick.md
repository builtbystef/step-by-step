---
id: m6s5me
title: 'Editor: the selector panel, hand editing, and Re-pick'
state: in-progress
priority: medium
labels:
    - needs-review
depends_on:
    - disgge
    - y2fsy1
parent: d8ux2s
created: 2026-08-14T06:03:58Z
updated: 2026-08-27T03:51:46Z
---

## What to build

The repair surface for targets. Each targeting Step's card carries a selector panel: collapsed, "How this step finds '<element>'" with a health badge; expanded, the ranked candidate list with per-candidate tools and two repair paths — re-picking the element on the live page through the extension, or hand-editing the candidates, which are plain stored data. Re-pick replaces one Step's candidate list and nothing else: the user navigates to the page themselves (the Workflow is not replayed to get there), clicks the intended element, and confirms old versus new in the editor.

## Acceptance criteria

- [ ] Collapsed panel shows the health badge: green "N ways to find it — verified when recorded", amber "fragile — only position-based selectors", red for unsupported targets with the recorded warning.
- [ ] Expanded panel lists candidates ranked best-first with kind chip, value, and uniqueness status, and offers move-to-top, remove, and add-selector-by-hand; hand edits save through the Draft API like any edit.
- [ ] "Pick element again…" starts a repick-scoped session handed to the extension; the user navigates to the page themselves and clicks the intended element; the extension computes a fresh verified candidate list and finalizes it to the session.
- [ ] The editor then shows old and new candidate lists side by side; confirming patches exactly that one Step in the Draft — its id and every other field preserved, no other Step touched (the worked example at the API seam).
- [ ] Cancelling the confirm leaves the Draft unchanged.

## Notes

**agent** — 2026-08-27T03:51:46Z

Implementation is blocked by a contract contradiction. This issue requires the editor to show old and new candidates after the extension finalizes the Re-pick, and requires confirmation to be the operation that patches the Draft while cancellation leaves it unchanged. Its completed dependency bysmhd instead requires—and the current POST /api/recording-sessions/{session_id}/finalize implements—Re-pick finalize as the operation that immediately patches the Draft. The viable options are: (1) change Re-pick finalize to stage/return candidates and add an explicit confirm operation that patches the Draft, revising bysmhd's recorded contract; or (2) keep finalize as the patch operation and have the extension send a preview to the editor before finalize, revising this issue's requirement that the extension finalize before confirmation. The user must choose one option, record the decision in a note, and remove the needs-review label.
