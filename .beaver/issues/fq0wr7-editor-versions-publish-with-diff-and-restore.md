---
id: fq0wr7
title: 'Editor: versions, publish with diff, and restore'
state: done
assignee: claude
priority: medium
depends_on:
    - g795ji
    - y2fsy1
parent: d8ux2s
created: 2026-08-14T06:04:08Z
updated: 2026-08-19T20:46:12Z
---

## What to build

The editor's version surface over the publish machinery. The header carries the Draft chip and a version dropdown; past Versions open read-only with a restore path; publishing walks through a modal that shows the step-level diff before minting.

## Acceptance criteria

- [ ] The header shows the Draft chip — amber "unpublished changes", green "in sync with vN" — driven by the derived draft state, and the version dropdown lists the Draft plus every Version.
- [ ] Selecting a past Version opens it read-only (no card edits, no drawer edits) with a restore-to-Draft action; restoring loads that Version's document into the Draft and returns to editing, with the chip reflecting the new comparison.
- [ ] Publish opens a modal rendering the step-level diff against the last Version — added, removed, and changed Steps by their labels — and confirming mints the next Version and flips the chip to in-sync; a first publish (no prior Version) shows every Step as added.
- [ ] Cancelling the modal mints nothing.

## Notes

**claude** — 2026-08-19T20:46:12Z

Done. The version surface over the publish machinery already built by `g795ji`: the header's dropdown, a Version opened read-only with a restore path, and the publish modal that shows the step diff before it mints.

**Seams.** Frontend only — `g795ji` owns every route this slice calls and covers all of them with 16 HTTP seam tests against a real Postgres, including the worked diff, the state transitions, restore, and "a first publish shows every Step as added". The spec rules editor UI automation out and this repo has no rendering stack, so the seam here is the same one `y2fsy1` and `5rkj33` took: the pure modules, read back with no DOM. 22 new Vitest tests across three modules. What that seam cannot observe is stated under "For a reviewer".

**What landed**

- `[id]/versions.ts` — the dropdown's entries (the Draft over every Version, newest first, one marked open), the address a choice opens, which Version an address is showing, and what restoring one costs.
- `[id]/publish.ts` — the backend's one `DraftComparison` arranged into what the modal states: the number about to be minted, the three lists with the empty ones dropped, and a sentence for each case a step diff cannot show.
- `[id]/publish-dialog.tsx`, `[id]/editor/restore-dialog.tsx` — the two confirms.
- `[id]/layout.tsx` — the header gains the version dropdown beside the Draft chip and a Publish button beside Run. `[id]/editor/page.tsx` — the same card list over a Version's document, behind a banner that says which one and offers the way back.
- `readOnly` reaches `step-card.tsx`, `step-form.tsx`, and `variables-drawer.tsx`.
- `[id]/editor/messages.ts` gains `readRefusal`, and the Draft's own read failure moves onto it — the screen was answering "the Draft was not saved" to a read that never wrote anything, which would have been a second wrongness once a Version could fail to load beside it.

**Decisions**

- **Which document is open lives in the address** (`?version=N`), for the reason the tabs are segments: a Version somebody is reading is a place, so it survives a reload and can be sent on. A query and not a fifth segment, because it is the same editor either way — a Version is a Draft that stopped changing, not a second screen about one.
- **Read-only is a disabled `fieldset`, not a prop on every control.** The step form and the drawer's rows each became one, so a Version cannot be edited through a control a later slice adds and forgets to thread a flag through. The tools that reorder, switch off, delete, and add are absent rather than disabled — a Version has no tools, and a row of dead buttons would claim it does. Expanding a card still works: reading a Version is the whole reason to open one.
- **The version dropdown is in the header, so it is on all four tabs**, and every entry lands in the editor. Reading a document is what the editor is for; the other three tabs are about Runs, and a Run pins its own Version.
- **Publish is refused while a Version is open**, with the reason in the tooltip. Publishing publishes the Draft, and a person reading v2 does not have it in front of them.
- **The modal refuses a publish that would mint an identical Version** (`in-sync`), and says so rather than hiding the button. Three other readings of an empty diff are distinguished, because they are genuinely different facts: a reorder- or Variables-only edit still differs (this is `g795ji`'s pinned pair of behaviours, surfaced), a first publish of an empty Draft has no Steps at all, and everything else is `null` and the sections speak.
- **The diff is fetched only while the modal is open.** A comparison of two whole documents is not something to keep warm behind a screen nobody opened. Nothing is minted by opening it — the read and the mint are two routes — which is what makes cancelling free.
- **Restore confirms first**, naming what is overwritten: the Draft, plus its unsaved edits when there are any. The Version is untouched and nothing that runs moves, and the sentence says that too, because "restore" reads like a rollback of what is live and is not one.
- **Unsaved edits survive a look at a Version.** The edited copy is kept while the address points elsewhere, so opening v2 out of curiosity does not cost an hour of editing.

**For a reviewer**

- `pnpm run ci` green (290 Vitest tests, 36 files). `pnpm test:integration` was not run — no Docker in this environment — and this slice changes no backend code, no `openapi.json`, and no generated client, so there is nothing there to drift.
- What the module seam does not observe, and what to check by eye: that the disabled fieldsets and the removed tools really leave a Version uneditable (`step-card.tsx`, `step-form.tsx`, `variables-drawer.tsx`), and that cancelling the publish modal mints nothing — true by construction, since the only caller of `publishWorkflowVersion` is the confirm button.
- An address naming a Version that does not exist (`?version=9`) shows the editor's "That Version is not here" callout while the dropdown trigger still reads "Draft". Left as is: the callout is the answer, and a second one in the trigger would say it twice.
- The Draft chip and its two hues were already `y2fsy1`/`5rkj33`'s `draft-state.ts`, tested there; this slice drives it from publish and restore rather than rebuilding it.
