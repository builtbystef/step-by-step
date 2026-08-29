---
id: vta7bn
title: 'Editor: a {{name}} nothing declares, surfaced where it is typed'
state: done
assignee: agent
priority: low
parent: d8ux2s
created: 2026-08-19T20:32:19Z
updated: 2026-08-29T08:08:45Z
---

## What to build

The Variables drawer lists what the Draft declares. It does not list the other half: a `{{name}}` a value reaches for that no declaration covers. That document is refused by the store (`undeclared_variable`), so today a person who hand-types `{{tenatn}}` into a URL learns it from a refused save at the bottom of the screen, and has to find the card again themselves.

Surface it where it is written: the drawer lists undeclared references beside the declarations, in the amber that already means "look at this", each with the Steps that use it and a one-click "Declare it" that adds the Variable (secret flag chosen there). The value field can say the same thing under the input it was typed into.

## Acceptance criteria

- [ ] A value referencing a name the document does not declare is listed in the drawer, flagged, with the Steps that use it.
- [ ] Declaring it from that row adds the Variable and clears the flag; nothing else in the document changes.
- [ ] A Draft with no undeclared references lists nothing extra — the section is absent rather than empty.

## Why it is not in z8p5dp

Found while building the drawer (`z8p5dp`). That issue's criteria are the declared side — list, declare, delete, rename, re-flag, insert, convert — and the store already refuses the document either way, so this is a better way of learning it and not a missing rule.

## Notes

**agent** — 2026-08-29T08:02:43Z

Seam: variables.ts, read back in variables.test.ts without a DOM — same as z8p5dp. The spec puts editor behavior at the API seam; the store already refuses undeclared_variable. This slice is the drawer's listing, the one-click declare, and the value-field hint, all derived from that same document walk.

**agent** — 2026-08-29T08:08:38Z

Done. A `{{name}}` nothing declares is listed in the Variables drawer (amber, with the Steps that use it) and under the value field it was typed into. Declaring it from that row adds the Variable and clears the flag; the Steps are untouched.

**Seams.** Same as z8p5dp: `variables.ts`, read back in `variables.test.ts` without a DOM. The store already refuses `undeclared_variable`; this slice is how a person learns it where they typed it. 6 new tests.

**What landed**

- `undeclaredRows` / `undeclaredNames` — the walk: every interpolating value, the names nothing declares, first-seen first, with the Steps that stand on each. `withVariableDeclared` is the declare; the Steps do not change, so the flag clears because the name is now declared.
- The drawer renders a "Not declared" section only when that list is non-empty — absent, not empty. Each row is amber (`wait`), shows `used by N steps`, and offers Declare it with the secret flag chosen there.
- The value field says the same under the input, in the same amber. Declaring stays on the drawer row.
- Highlight-and-scroll from an undeclared row uses the same usage band as a declared one.

**Decisions**

- **Declare is the existing edit.** A new operation that also rewrote values would be a different change; the person already wrote the `{{name}}`. Adding the declaration is the whole fix.
- **The section is omitted, not stubbed.** An empty "Not declared" heading would be a thing to look at when there is nothing to look at.
- **Select values still do not interpolate.** `{{country}}` on a choose-from-a-list Step is text, so it is not listed — the same reading `variableRows` already uses.

**For a reviewer**

- `pnpm check` and `pnpm test` green (546 fast tests). No API or generated-client change.
- Look at `variables-drawer.tsx` (the Not declared section) and `value-field.tsx` (the hint under the input). The decisions behind both are in `variables.ts`.
