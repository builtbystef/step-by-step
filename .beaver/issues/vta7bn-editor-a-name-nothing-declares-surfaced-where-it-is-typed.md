---
id: vta7bn
title: 'Editor: a {{name}} nothing declares, surfaced where it is typed'
state: todo
priority: low
parent: d8ux2s
created: 2026-08-19T20:32:19Z
updated: 2026-08-19T20:32:19Z
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
