---
id: y2fsy1
title: 'Editor: the card list and Draft editing'
state: todo
priority: medium
depends_on:
    - sl7h4j
    - 5rkj33
    - 8cjj8g
parent: d8ux2s
created: 2026-08-14T06:03:23Z
updated: 2026-08-14T06:03:23Z
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
