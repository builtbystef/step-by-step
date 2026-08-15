---
id: z8p5dp
title: 'Editor: the Variables drawer and pills'
state: todo
priority: medium
depends_on:
    - y2fsy1
parent: d8ux2s
created: 2026-08-14T06:03:47Z
updated: 2026-08-14T06:03:47Z
---

## What to build

Variables as a first-class editing surface. A drawer declares Variables (name, secret flag) inside the Draft document; step values reference them as pills that mix freely with literal text. The drawer shows where each Variable is used and refuses to delete one that is still referenced — surfacing the document-validation rule the store already enforces. Masking keys off the Variable's secret flag, never the syntax.

## Acceptance criteria

- [ ] The drawer lists declared Variables with name and secret flag; declaring one adds it to the Draft document; each row shows "used by N steps", and activating it highlights and scrolls to the usages.
- [ ] Deleting a Variable used by any Step is refused with the reason; an unused Variable is flagged amber and deletable.
- [ ] A dropdown inserts `{{name}}` pills into type values and navigate URLs; a value can mix literal text and several pills; the sentence summaries render the pills.
- [ ] Secret-Variable pills are styled distinctly from plain ones; converting a recorded literal value into a Variable is possible from the value field.
- [ ] Renaming or re-flagging happens through the document save and is reflected in every referencing card.
