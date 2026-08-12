---
id: tf6796
title: 'Prototype: how does a user create a Batch from a list of rows?'
state: todo
priority: medium
labels:
    - roadmap:idnzwf
    - session:prototype
depends_on:
    - apx4rs
    - kvz5sv
parent: idnzwf
created: 2026-08-12T01:03:42Z
updated: 2026-08-12T01:03:42Z
---

Live prototype session (prototype skill). Batch *execution* is settled — spec 9gea5p owns the sequential row loop, skip, re-run-a-row, cancel, ETA, and the batch progress table (apx4rs). What no node has answered is how a Batch comes into existence. Answer with disposable UI:

- How does a user get rows in: typing them, pasting a table, uploading a CSV, or all three?
- How are the file's columns mapped onto the Workflow's declared Variables, and what does a mismatch look like (a missing Variable, an extra column, an empty cell)?
- What does the user see before committing — a preview of the rows, a count, the Variables each row will fill?
- How is a Batch named, and how does a user start a new Batch from an old one's rows?
- Where does the rule that secret Variables never travel in rows (8iuuh8) become visible, rather than a surprise at run time?
- What happens when the Workflow's Variables change after a Batch was created?

Inputs: the batch half of spec 9gea5p, the progress-view verdict in apx4rs, ds8zyn's Variable model, docs/GLOSSARY.md. The result feeds the spec for this area.
