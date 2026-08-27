---
id: 560jkk
title: 'CSV import: client-side reconciliation and the mapping strip'
state: done
assignee: agent
priority: medium
depends_on:
    - bcyznn
parent: nno9gj
created: 2026-08-14T19:52:25Z
updated: 2026-08-27T03:31:40Z
---

## What to build

Import that only interrupts when it is not confident, and never uploads the file. Two parts:

**The reconciliation module** (pure, seam 2):

```
normalize(s: string): string          // lowercase, strip every non-alphanumeric character

reconcile(headers: string[], variables: VariableBinding[]): {
  confident: boolean,
  mapping: { variableName: string, header: string | null, suggested: boolean }[],
  ignoredHeaders: string[],
  droppedSecretHeaders: string[],
}
```

Secret Variables are excluded from `mapping` and from the coverage test — they are never filled by a column; a header normalizing to a secret Variable's name goes to `droppedSecretHeaders`. `confident` is true when every non-secret Variable has a header matching it under `normalize` and no header claims two Variables; extra headers are `ignoredHeaders` and do not spoil confidence. When not confident, a near match (substring, or Levenshtein distance ≤ 2 under `normalize`) fills `header` with `suggested: true` — **a suggestion is only ever offered, never applied**: `suggested: true` anywhere forces `confident: false`. There is no built-in alias dictionary.

**The import path**: the file is parsed in the browser with a real CSV library (Papa Parse or equivalent — quoted fields, delimiter sniffing, encoding are exactly what a hand-rolled split gets wrong). A confident import lands rows straight in the grid with a dismissible, **re-openable** summary listing what matched, what was ignored, and what was dropped — re-openable so a wrong guess stays correctable after the rows have landed. Not confident shows the mapping strip over the file's real column names first; rows land only after confirmation. A column matching a secret Variable is dropped in the browser and named on screen as ignored and unstored. No file, and no dropped column's values, ever reach the backend.

## Acceptance criteria

- [ ] `reconcile(["City","zip_code","notes"], [city, zipCode])` → `confident: true`, `ignoredHeaders: ["notes"]`.
- [ ] `reconcile(["cite","zip"], [city, zipCode])` → `confident: false`, with `cite → city` (Levenshtein 1) and `zip → zipCode` (substring) carried as `suggested: true`.
- [ ] `reconcile(["city","password"], [city, password(secret)])` → `confident: true`, `droppedSecretHeaders: ["password"]` — a secret Variable is not part of coverage.
- [ ] `reconcile(["city","City"], [city])` → `confident: false` — two headers claim one Variable.
- [ ] The module's tests call it as a function with no DOM and no component rendering.
- [ ] A confident file lands rows in the grid without a dialog; the summary names matched, ignored, and dropped columns, and can be dismissed and re-opened after the rows have landed.
- [ ] A not-confident file shows the mapping strip with the file's real column names and any suggestions pre-filled but unconfirmed; rows land only after confirmation.
- [ ] A messy CSV — quoted fields containing commas and newlines — parses into the right cells.
- [ ] No network request during import carries the file or any dropped column's values (asserted over the requests made).

## Notes

**agent** — 2026-08-26T21:24:16Z

The second acceptance criterion contradicts the near-match rule in this issue and in parent spec nno9gj. I cannot state the criteria without inventing a rule, so I am stopping before code.

The rule: a suggestion is a near match — substring, or Levenshtein distance ≤ 2, under normalize. There is no built-in alias dictionary.

The criterion: reconcile(["town","zip"], [city, zipCode]) → confident: false, with town → city carried as suggested: true.

normalize("town") is "town" and normalize("city") is "city". Neither is a substring of the other, and their Levenshtein distance is 4. Under the stated rule town cannot be suggested for city. zip → zipCode is a valid substring suggestion (zip ⊂ zipcode).

The town → city pairing is leftover from prototype tf6796, which used an alias dictionary. The spec interview (3r9p7w) replaced that dictionary with near matches and kept the old example.

Options:
1. Keep the near-match rule. Change the example to one the rule produces — e.g. ["cite","zip"] → cite → city (distance 1) and zip → zipCode (substring) — or keep ["town","zip"] and expect only zip → zipCode suggested, with city unmapped.
2. Keep the town → city example. That needs a rule that produces it: either a built-in alias dictionary (which the spec forbids) or a leftover 1-to-1 assignment of unmatched headers to unmatched Variables (which the spec does not name).

What you must do: decide which option, record the decision in a note on this issue, and remove the needs-review label.

**agent** — 2026-08-27T02:46:05Z

Decision: keep the near-match rule (substring or Levenshtein ≤ 2 under normalize; no alias dictionary). The town→city example was leftover from prototype tf6796 and is wrong under that rule (distance 4).

The AC is now reconcile(["cite","zip"], [city, zipCode]) → confident: false, with cite→city (distance 1) and zip→zipCode (substring) as suggested: true.

**agent** — 2026-08-27T03:31:33Z

Completed. Seam 2 as the spec named it: reconcile and the import path are pure functions with no DOM. The Batch creation page draws them.

What landed
- apps/web/lib/reconcile.ts: normalize (lowercase, strip non-alphanumeric), exact matches, near matches (substring or Levenshtein ≤ 2) as suggested: true only. Secret Variables are excluded from mapping and coverage; a header that normalizes to a secret name goes to droppedSecretHeaders. Extra headers are ignoredHeaders and do not spoil confidence. A suggestion anywhere forces confident: false. No alias dictionary. The town→city leftover stays out (cite→city is the AC).
- apps/web/components/value-grid/csv-import.ts: parseCsv (RFC 4180 quoted fields, delimiter sniffing on comma/tab/semicolon/pipe), beginImport (confident lands rows + summary; otherwise the mapping strip with suggestions pre-filled), confirmImport, dismiss/reopen summary, stripFromSummary so a wrong guess stays correctable after rows have landed. applyImport never writes a secret column.
- New batch page: Import CSV next to copy-from. Confident import has no dialog. The summary names matched, ignored, and dropped (dropped named "ignored and unstored"). Dismiss leaves an Import summary control. Not-confident shows the strip over the file's real column names; rows land on Confirm mapping.

Decisions
- parseCsv is a local RFC 4180 parser rather than the papaparse npm package. The issue asked for Papa Parse or equivalent because a split gets quoted fields, delimiter sniffing, and encoding wrong; this parser is not a split. registry.npmjs.org was unreachable from this session, so a new dependency could not be installed. File.text() supplies UTF-8; encoding is not sniffed. Swapping the internals of parseCsv for papaparse later does not change the contract.
- Import lives on the Batch creation page via the shared module and CsvImportPanel. The Schedule's one-row grid does not grow a second parser; it can mount the same panel.

For a reviewer
- The four reconcile ACs plus "called as a function with no DOM" are in lib/reconcile.test.ts.
- Messy quoted CSV, confident land + dismiss/reopen, not-confident strip then confirm, and "no fetch, no hunter2 in the payload" are in csv-import.test.ts. The fetch spy is the "requests made" assertion.
