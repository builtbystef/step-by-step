---
id: z8p5dp
title: 'Editor: the Variables drawer and pills'
state: done
assignee: claude
priority: medium
depends_on:
    - y2fsy1
parent: d8ux2s
created: 2026-08-14T06:03:47Z
updated: 2026-08-19T20:32:43Z
---

## What to build

Variables as a first-class editing surface. A drawer declares Variables (name, secret flag) inside the Draft document; step values reference them as pills that mix freely with literal text. The drawer shows where each Variable is used and refuses to delete one that is still referenced — surfacing the document-validation rule the store already enforces. Masking keys off the Variable's secret flag, never the syntax.

## Acceptance criteria

- [ ] The drawer lists declared Variables with name and secret flag; declaring one adds it to the Draft document; each row shows "used by N steps", and activating it highlights and scrolls to the usages.
- [ ] Deleting a Variable used by any Step is refused with the reason; an unused Variable is flagged amber and deletable.
- [ ] A dropdown inserts `{{name}}` pills into type values and navigate URLs; a value can mix literal text and several pills; the sentence summaries render the pills.
- [ ] Secret-Variable pills are styled distinctly from plain ones; converting a recorded literal value into a Variable is possible from the value field.
- [ ] Renaming or re-flagging happens through the document save and is reflected in every referencing card.

## Notes

**claude** — 2026-08-19T20:32:43Z

Done. Variables as a first-class editing surface: a drawer over the card list, `{{name}}` pills in the two values that interpolate them, and a literal a recording captured made into a Variable from the field it was recorded into.

**Seams.** The spec puts editor behavior at the API seam and rules out DOM automation, and the two rules this slice leans on are already asserted there: a save whose value references a name the document does not declare is refused (`test_a_value_referencing_a_variable_nothing_declares_is_refused` — its docstring is this drawer's delete rule), and two Variables under one name are refused. So no backend change and no new integration test; what is new is frontend decisions, read back without a DOM the way `y2fsy1` set the precedent. 12 new Vitest tests in `variables.test.ts`, 2 in `steps.test.ts`.

**What landed**

- `variables.ts` — the decisions: `variableRows` (each declaration with the Steps that stand on it), `declarationRefusal` and `deletionRefusal` (the store's two rules, said before the save), `withVariableDeclared` / `withVariableDeleted` / `withVariableRenamed` / `withVariableSecret`, `withReferenceInserted`, `withLiteralMadeVariable`, and `secretNames`. It also owns `REFERENCE`, which `summary.ts` now imports rather than keeping a second copy of — the pills a sentence draws and the usages the drawer counts must be the same reading.
- `steps.ts` gains `interpolatedValue` / `withInterpolatedValue`: the navigate URL and the type value, which are the two the store interpolates and therefore the two a Variable control belongs on.
- `variables-drawer.tsx` — the Sheet: name, secret flag, "used by N steps", delete, and the declare form in the footer.
- `value-field.tsx` — the field for an interpolated value: a dropdown that writes `{{name}}` at the caret, and "Make a Variable of this value…", which declares and replaces in one edit.
- `sentence.tsx` draws a secret pill filled in under a key; `step-card.tsx` lights the Steps a drawer row points at and scrolls the first into view; `page.tsx` carries the drawer, the highlight band, and the count on the Variables button.
- `docs/ARCHITECTURE.md` gained the drawer beside the card list.

**Decisions**

- **A rename rewrites the values, not just the declaration.** Renaming the row alone would leave every value reaching for a name nothing declares — the document the store refuses. So it is one edit over the whole document, which is also what makes it show up on every referencing card: they read the same document.
- **Refusals are said in the drawer, not waited for from the save.** The store's message is about a document; the drawer's is "2 Steps still use {{password}}. Change those values first." Same rule, said where the person can act on it. Deleting a used Variable and declaring a name already taken are both refused this way, in place, without touching the document.
- **Converting a literal is one operation.** Declare-then-replace as two steps would put the document through a state the store refuses, and the person is doing one thing anyway: this typed-in account name is an input. `withLiteralMadeVariable` does both, over the run of text that was selected — or the whole value, which is what a recorded literal usually is.
- **Secret is the flag and never the syntax.** Pills are drawn from `secretNames`, so a Variable called `secret_note` is plain and a Variable called `t` can be the password. Re-flagging alone changes what is masked; no value changes.
- **Activating a usage count closes the drawer.** It highlights the cards behind it, and a modal panel over the thing it is pointing at would be pointing at nothing. A band above the list says which Variable is lit and dismisses the highlight.
- **The caret is remembered in a ref.** A menu item takes the focus off the field before it is clicked, so the field cannot be asked afterwards where the caret was.

**Deliberately not here, and where to**

- A `{{name}}` nothing declares, surfaced in the drawer instead of only at a refused save — found while building this, published as `vta7bn`.
- Masking secret values in the test-run form (`2ggmhx`), and the Secrets vault a secret Variable binds to (`7o0nmx`).
- The selector panel (`m6s5me`), recording (`7vuup5`), publish (`fq0wr7`).

**For a reviewer**

- `pnpm run ci` green; 267 fast tests. No `openapi.json` or generated-client change: this slice adds no endpoint.
- No DOM test exists for the drawer or the value field. What to look at by eye is `variables-drawer.tsx` and `value-field.tsx` — every decision behind them is in `variables.ts` and read back there.
