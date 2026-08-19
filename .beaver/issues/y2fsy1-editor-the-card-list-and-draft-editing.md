---
id: y2fsy1
title: 'Editor: the card list and Draft editing'
state: done
assignee: claude
priority: medium
depends_on:
    - sl7h4j
    - 5rkj33
    - 8cjj8g
parent: d8ux2s
created: 2026-08-14T06:03:23Z
updated: 2026-08-19T20:21:00Z
---

## What to build

The Editor tab's content: the Draft rendered as a vertical inline card list that reads as sentences. Each card's summary is a narrative line with Variable pills and target tokens ("Type {{password}} into Password field") under a bold editable label; clicking expands the full form in place; hover tools reorder, disable, and delete; the right-hand badge column carries optional / off / timeout override / screenshot, plus the red unsupported and amber fragile badges rendered from the document (the selector panel behind them is a later slice). Steps can also be added in the editor with app-minted ids — the way wait and pause-for-takeover Steps enter a Workflow. Everything saves through the Draft API. The layout is prototype 3iwv5i's variant A; editor behavior is tested at the API seam, not with DOM automation.

## Acceptance criteria

- [ ] The Editor tab loads the Draft and renders one card per Step in order, summary sentences with Variable pills and target tokens, labels editable inline.
- [ ] Every one of the eight step types expands to an editable form covering its payload — including navigate URL, type/select values, extract mode with fields, wait duration-or-element, and pause-for-takeover message, timeout, and success-check target — plus the envelope: optional, disabled, timeout override (shown falling back to the workflow default of 30 s), and the screenshot toggle in the badge column.
- [ ] Reorder, disable, and delete work from hover tools; disabled Steps stay visibly in the list.
- [ ] Adding a Step in the editor mints a fresh id; edits never rewrite existing ids.
- [ ] Saves go through the Draft API; a rejected save (duplicate id, undeclared Variable reference) surfaces the backend's error instead of silently dropping.
- [ ] A Step whose target carries the unsupported flag shows the red badge with its recorded plain-language warning; a Step with only position-based selectors shows the amber fragile badge.

## Notes

**claude** — 2026-08-19T20:21:00Z

Done. The Editor tab: the Draft as a card list that reads as sentences, every Step's form in place, and saving through the Draft API.

**Seams.** The spec rules editor UI automation out and puts editor behavior at the API seam, so: the pure frontend modules read back with no DOM (the precedent 5rkj33 set — this repo has no rendering stack), and the backend HTTP API against a real Postgres for the two things that are actually contract. 34 new Vitest tests across six modules; two new integration tests.

**What landed**

- `apps/web/app/(shell)/workflows/[id]/editor/` — `page.tsx` (the tab: one edited copy of the document, the add menu, the sticky save footer), `step-card.tsx` (label, sentence, hover tools, badge column), `step-form.tsx` (the eight payloads and the envelope), `sentence.tsx` (pills and tokens), `queries.ts`.
- The decisions, each read back by a test: `steps.ts` (what the eight types are called, `targetsOf`, `blankStep`), `edits.ts` (reorder / delete / add / replace), `summary.ts` (a Step as segments), `badges.ts` (the column, and `targetHealth`), `messages.ts` (a refused save).
- `apps/web/lib/duration.ts` — milliseconds as words, shared by the wait sentence, the timeout badge, and the fallback hint.
- `WorkflowSummary` gains `default_step_timeout_ms`, so the fallback under an empty timeout field is this Workflow's number rather than a 30 s the frontend knows by heart. One integration test; `openapi.json` and the generated client are regenerated.
- `docs/ARCHITECTURE.md` gained the editor beside the list it sits under.

**Decisions**

- **Nothing saves as you type.** A save replaces the Draft whole and validates it whole, so the screen holds one edited copy, every tool hands back the next document, and the footer sends it. Saving per keystroke would be a hundred rejected documents on the way to one good one. The edited copy also wins over a background refetch, so a refetch cannot take unsaved work away.
- **A refused save keeps the backend's message.** Every other screen picks a sentence by `code` and drops the prose. Here the prose is the only thing that says which Step of a hundred carries the duplicate id, or which `{{name}}` nothing declares, so the sentence is chosen by code and the message is appended to it.
- **The add menu offers three types, not eight** — navigate, wait, pause-for-takeover: the ones that point at no element. The other five need a verified candidate list, which only a recording or a Re-pick produces, so minting one here would be a Step this editor cannot finish. Same reason a `wait` Step does not switch between its duration and element modes. Published as `al0icb`, blocked by `m6s5me`.
- **Fragile is "every candidate is CSS".** The seven kinds above CSS in the ranking were read from something the page says out loud; a target that offered none of them is one position alone can find. Unsupported outranks it and is never computed — it is the recorder's flag, and the badge carries the recorder's own plain-language warning (also as a Callout inside the expanded card).
- **The screenshot toggle is a control in the badge column**, per the spec's amendment, and it is the only thing in that column a person operates rather than reads. It is lit when on and appears with the hover tools when off — a column of eight dormant cameras states nothing.
- **A cleared optional field travels as an explicit `null`.** The editor sends back the document it read, so emptying a field cannot make a key vanish. Tested at the seam: it is accepted and reads back absent, which is what absence means in this document. Mutation-checked (making `message` non-optional fails it).

**Deliberately not here, and where to**

- The selector panel behind a target's badge, hand-editing candidates, and Re-pick — `m6s5me`. This form shows what a Step finds its element by and how many ways there are to it, and never pretends the list is empty.
- The Variables drawer, pill insertion, and secret styling — `z8p5dp`. The sentence already draws a `{{name}}` as a pill in the human hue.
- Recording into the Draft (`7vuup5`), test runs and Selector Drift (`2ggmhx`), the version dropdown and publish (`fq0wr7`).
- A guard on leaving with unsaved edits — found while building this, published as `iv65m1`.

**For a reviewer**

- `pnpm run ci` green; `pnpm test:integration` 140 + 5 passing.
- The sentence tests carry the spec's own worked example ("Type {{password}} into Password"), and every edit test reads the Step ids back — that is the id-stability criterion, asserted rather than assumed.
- No DOM test exists for the card list; what a reviewer should look at by eye is `step-card.tsx` and `step-form.tsx` against prototype `3iwv5i`'s variant A.
