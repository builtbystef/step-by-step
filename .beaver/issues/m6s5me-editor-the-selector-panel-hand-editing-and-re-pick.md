---
id: m6s5me
title: 'Editor: the selector panel, hand editing, and Re-pick'
state: todo
priority: medium
depends_on:
    - disgge
    - y2fsy1
parent: d8ux2s
created: 2026-08-14T06:03:58Z
updated: 2026-08-14T06:03:58Z
---

## What to build

The repair surface for targets. Each targeting Step's card carries a selector panel: collapsed, "How this step finds '<element>'" with a health badge; expanded, the ranked candidate list with per-candidate tools and two repair paths — re-picking the element on the live page through the extension, or hand-editing the candidates, which are plain stored data. Re-pick replaces one Step's candidate list and nothing else: the user navigates to the page themselves (the Workflow is not replayed to get there), clicks the intended element, and confirms old versus new in the editor.

## Acceptance criteria

- [ ] Collapsed panel shows the health badge: green "N ways to find it — verified when recorded", amber "fragile — only position-based selectors", red for unsupported targets with the recorded warning.
- [ ] Expanded panel lists candidates ranked best-first with kind chip, value, and uniqueness status, and offers move-to-top, remove, and add-selector-by-hand; hand edits save through the Draft API like any edit.
- [ ] "Pick element again…" starts a repick-scoped session handed to the extension; the user navigates to the page themselves and clicks the intended element; the extension computes a fresh verified candidate list and finalizes it to the session.
- [ ] The editor then shows old and new candidate lists side by side; confirming patches exactly that one Step in the Draft — its id and every other field preserved, no other Step touched (the worked example at the API seam).
- [ ] Cancelling the confirm leaves the Draft unchanged.
