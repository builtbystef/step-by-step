---
id: 0zwbku
title: Workflow documents preserve omitted envelope fields across round trips
state: done
assignee: agent
priority: high
labels:
    - bug
created: 2026-08-24T10:13:30Z
updated: 2026-08-24T16:33:44Z
---

## Problem

A sparse Step accepted from the editor or recorder reads back with default envelope fields such as `optional: false`, `disabled: false`, and `screenshot: false` added. This contradicts the Workflow wire contract in `docs/ARCHITECTURE.md`: a field nobody set is absent, and a Draft reads back as the document that was saved. The inflation appears in recording finalization and in a test Run's `draft_snapshot`.

## Acceptance criteria

- [ ] Saving and reading a sparse Workflow document returns the same document without materializing omitted Step envelope fields.
- [ ] Finalizing a recording from sparse checkpoint Steps returns and stores those Steps byte-for-byte in document shape.
- [ ] A test Run's `draft_snapshot` preserves the sparse Draft document.
- [ ] Internal execution still observes the documented defaults when validating a sparse document.
- [ ] The recording-session and Run integration examples that currently compare against their sparse inputs pass, and the full API integration tier is green apart from failures owned by another explicit issue.

## Evidence

`pnpm test:integration` on 2026-08-24: two recording-session assertions and `test_test_and_manual_runs_store_the_document_they_execute` received Pydantic-materialized default envelope fields not present in the input.

## Notes

**agent** — 2026-08-24T16:33:44Z

Completed sparse Workflow document preservation across Draft saves/reads, recording finalization, Version reads/restores, duplication, and test Run snapshots. Storage and HTTP serialization now omit fields Pydantic defaulted while retaining explicitly supplied default values; top-level steps and variables remain present. Added an integration round-trip example and a shared document-contract test proving Workers still observe false/None execution defaults. Verified pnpm check, pnpm test, pnpm build, and the full integration tier (API 169 passed; core 5 passed).
