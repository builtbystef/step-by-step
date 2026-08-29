---
id: m6s5me
title: 'Editor: the selector panel, hand editing, and Re-pick'
state: done
assignee: agent
priority: medium
depends_on:
    - disgge
    - y2fsy1
parent: d8ux2s
created: 2026-08-14T06:03:58Z
updated: 2026-08-29T06:48:29Z
---

## What to build

The repair surface for targets. Each targeting Step's card carries a selector panel: collapsed, "How this step finds '<element>'" with a health badge; expanded, the ranked candidate list with per-candidate tools and two repair paths — re-picking the element on the live page through the extension, or hand-editing the candidates, which are plain stored data. Re-pick replaces one Step's candidate list and nothing else: the user navigates to the page themselves (the Workflow is not replayed to get there), clicks the intended element, and confirms old versus new in the editor.

Re-pick confirm is the existing recording finalize, not a second write. The extension never calls finalize on click: it returns the new candidate list to the editor tab. The editor shows old versus new; confirming is `POST /api/recording-sessions/{id}/finalize` with that list (bysmhd's contract, unchanged); cancelling never calls it, so the Draft is untouched. Hand-edits still save through the Draft API like any edit. Refuse to mint a Re-pick session while the editor has unsaved edits — finalize patches the server Draft, and a dirty local copy would race it.

## Acceptance criteria

- [ ] Collapsed panel shows the health badge: green "N ways to find it — verified when recorded", amber "fragile — only position-based selectors", red for unsupported targets with the recorded warning.
- [ ] Expanded panel lists candidates ranked best-first with kind chip, value, and uniqueness status, and offers move-to-top, remove, and add-selector-by-hand; hand edits save through the Draft API like any edit.
- [ ] "Pick element again…" is refused while the editor has unsaved edits. Otherwise it starts a repick-scoped session handed to the extension; the user navigates to the page themselves and clicks the intended element; the extension computes a fresh verified candidate list and messages it to the editor tab — it does not call finalize.
- [ ] The editor then shows old and new candidate lists side by side; confirming is the existing Re-pick finalize and patches exactly that one Step in the Draft — its id and every other field preserved, no other Step touched (the worked example at the API seam).
- [ ] Cancelling the confirm never calls finalize, so the Draft is unchanged.

## Notes

**agent** — 2026-08-27T03:51:46Z

Implementation is blocked by a contract contradiction. This issue requires the editor to show old and new candidates after the extension finalizes the Re-pick, and requires confirmation to be the operation that patches the Draft while cancellation leaves it unchanged. Its completed dependency bysmhd instead requires—and the current POST /api/recording-sessions/{session_id}/finalize implements—Re-pick finalize as the operation that immediately patches the Draft. The viable options are: (1) change Re-pick finalize to stage/return candidates and add an explicit confirm operation that patches the Draft, revising bysmhd's recorded contract; or (2) keep finalize as the patch operation and have the extension send a preview to the editor before finalize, revising this issue's requirement that the extension finalize before confirmation. The user must choose one option, record the decision in a note, and remove the needs-review label.

**agent** — 2026-08-27T06:33:44Z

Decision: option 2. Keep bysmhd's Re-pick finalize as the Draft write. The extension messages the new candidate list to the editor on click and does not finalize; the editor shows old vs new; confirm is POST /api/recording-sessions/{id}/finalize with that list; cancel never calls it. bysmhd is unchanged. Refuse to mint a Re-pick session while the editor has unsaved edits, so finalize cannot race a dirty local copy. Acceptance criteria revised to match. needs-review dropped.

**agent** — 2026-08-29T06:21:59Z

Returned to todo so an implement session can claim it. Decision (option 2) is recorded; needs-review is gone; dependencies disgge and y2fsy1 are done. Nothing is in progress on it.

**agent** — 2026-08-29T06:48:22Z

Done. The selector panel, hand-editing, and Re-pick (option 2: extension messages candidates, editor confirm is the existing finalize).

**Seams.** Spec puts editor UI automation out of scope, so: pure frontend modules read back with no DOM (selectors.ts — health wording, candidate tools, the unsaved-Re-pick sentence); the protocol names test; recording.js shape of a pending Re-pick; and the extension boundary (a Re-pick click messages candidates and never checkpoints or finalizes). Re-pick finalize itself is bysmhd's HTTP seam, unchanged.

**What landed**

- `apps/web/.../editor/selectors.ts` — health copy (green N ways / amber fragile / red recorded warning), candidate move-to-top / remove / add, `repickRefusal`.
- `selector-panel.tsx` — collapsed header with the health badge; expanded ranked rows (kind chip, value, unique); Pick element again…; add-by-hand.
- `repick-dialog.tsx` — old vs new; confirm is finalize; cancel never calls it.
- Editor page mints `mode: "repick"` only when the Draft is saved; the extension returns candidates on click and does not finalize.
- Extension: `readPendingRecording` accepts `mode: "repick"` + `stepId`; a Re-pick click broadcasts `repick-candidates` and clears local state. Popup copy distinguishes re-pick from record.

**Decisions**

- Uniqueness is always "unique": every persisted candidate was verified at capture, and the document has no second field.
- Re-pick is offered only for `payload.target` (bysmhd patches that). A pause's success check is hand-editable only.
- The panel header is a `<summary>` so it still opens inside a Version's disabled fieldset; the tools that rewrite the list are buttons, so they do not.
- Confirm uses the minted recording token against the existing finalize. Cancel drops the preview.

**For a reviewer**

- `pnpm check` and `pnpm test` green. Extension browser tier 25 passed, including the Re-pick click that asserts no finalize and no checkpoint.
- Health-copy tests use the spec's own sentences. Candidate-edit tests read the list back — rank and identity, not an internal rewrite.
- No DOM test for the panel; look at `selector-panel.tsx` against prototype `3iwv5i`'s selector panel.
