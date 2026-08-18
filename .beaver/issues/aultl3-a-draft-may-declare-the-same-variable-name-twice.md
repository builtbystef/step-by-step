---
id: aultl3
title: A Draft may declare the same Variable name twice
state: done
assignee: claude
priority: low
parent: d8ux2s
created: 2026-08-18T10:34:45Z
updated: 2026-08-18T23:15:44Z
---

## What to build

Draft save validation (`sl7h4j`) refuses a repeated Step id and a `{{name}}` that `variables` does not declare, but says nothing about two Variables with the same name. `[{"name": "password", "secret": true}, {"name": "password", "secret": false}]` saves today.

That is ambiguous where it matters most: secret masking keys off the Variable's secret flag, so which of the two rows a reader picks decides whether a value is masked in the test-run form, in logs, and in a Batch's rows. The Variables drawer's "used by N steps" and its delete refusal read the same list.

The fix is the same shape as the duplicate-id rule, in `step_by_step_api.workflows.document.validated()`.

## Acceptance criteria

- [ ] A Draft save whose `variables` declares one name twice is refused with a machine-readable code that names the repeated name.
- [ ] Names are compared as written — `Password` and `password` are two names, because `{{name}}` interpolation matches exactly.
- [ ] An HTTP seam test covers the refusal.

## Notes

**claude** — 2026-08-18T23:15:44Z

Refused with duplicate_variable_name in validated(), read before the Step loop so the declaration list is settled before anything is read against it. Names compared as written. Two seam tests: the refusal, and Password/password saving as two Variables.
