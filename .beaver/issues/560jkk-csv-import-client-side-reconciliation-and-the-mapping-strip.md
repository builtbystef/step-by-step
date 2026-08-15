---
id: 560jkk
title: 'CSV import: client-side reconciliation and the mapping strip'
state: todo
priority: medium
depends_on:
    - bcyznn
parent: nno9gj
created: 2026-08-14T19:52:25Z
updated: 2026-08-14T19:52:25Z
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
- [ ] `reconcile(["town","zip"], [city, zipCode])` → `confident: false`, with `town → city` carried as `suggested: true`.
- [ ] `reconcile(["city","password"], [city, password(secret)])` → `confident: true`, `droppedSecretHeaders: ["password"]` — a secret Variable is not part of coverage.
- [ ] `reconcile(["city","City"], [city])` → `confident: false` — two headers claim one Variable.
- [ ] The module's tests call it as a function with no DOM and no component rendering.
- [ ] A confident file lands rows in the grid without a dialog; the summary names matched, ignored, and dropped columns, and can be dismissed and re-opened after the rows have landed.
- [ ] A not-confident file shows the mapping strip with the file's real column names and any suggestions pre-filled but unconfirmed; rows land only after confirmation.
- [ ] A messy CSV — quoted fields containing commas and newlines — parses into the right cells.
- [ ] No network request during import carries the file or any dropped column's values (asserted over the requests made).
