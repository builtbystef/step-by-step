---
id: tf6796
title: 'Prototype: how does a user create a Batch from a list of rows?'
state: done
assignee: claude
priority: medium
labels:
    - roadmap:idnzwf
    - session:prototype
depends_on:
    - apx4rs
    - kvz5sv
parent: idnzwf
created: 2026-08-12T01:03:42Z
updated: 2026-08-12T01:24:06Z
---

Live prototype session (prototype skill). Batch *execution* is settled — spec 9gea5p owns the sequential row loop, skip, re-run-a-row, cancel, ETA, and the batch progress table (apx4rs). What no node has answered is how a Batch comes into existence. Answer with disposable UI:

- How does a user get rows in: typing them, pasting a table, uploading a CSV, or all three?
- How are the file's columns mapped onto the Workflow's declared Variables, and what does a mismatch look like (a missing Variable, an extra column, an empty cell)?
- What does the user see before committing — a preview of the rows, a count, the Variables each row will fill?
- How is a Batch named, and how does a user start a new Batch from an old one's rows?
- Where does the rule that secret Variables never travel in rows (8iuuh8) become visible, rather than a surprise at run time?
- What happens when the Workflow's Variables change after a Batch was created?

Inputs: the batch half of spec 9gea5p, the progress-view verdict in apx4rs, ds8zyn's Variable model, docs/GLOSSARY.md. The result feeds the spec for this area.

## Notes

**claude** — 2026-08-12T01:24:06Z

VERDICT (user's words: "I agree with all this") — a Batch is created on a **grid-first** page whose columns ARE the Workflow's Variables. Branch `prototype/batch-creation`, file `PROTOTYPE-batch-creation.html` (three variants: A wizard, B composer, C grid-first).

THE FRAME — the destination table exists before any file does, because a Workflow's Variables are a small, fixed, known schema. So the grid is always there: typing rows by hand, pasting, importing a CSV, and copying a past Batch's rows are the same surface, not four flows. Rejected: variant A's staged modal wizard (it sequences decisions that usually do not exist, and it makes the two cheapest flows — type three rows, reuse an old Batch — the most expensive); a permanent mapping screen on every import.

MAPPING IS AN EXCEPTION, NOT A STEP — import runs a reconciliation. Confident (every Variable matched by exact header name, no Variable left uncovered) → rows land straight in the grid with a dismissible, re-openable summary listing what matched, what was ignored, and what was dropped. Not confident (a name-alias guess such as `town` -> `city`, a Variable with no candidate, two plausible columns) → variant B's mapping strip is shown over the file's real column names FIRST, and rows land only after confirmation. One surface, shown on the exception. The summary stays re-openable so a wrong guess is correctable after rows have landed.

SECRETS — the secret Variable is a permanently visible **locked column** in the grid ("from vault"), so "a secret never travels in a Batch's row" (8iuuh8) is a standing property of the surface, not a warning that only fires when a file happens to carry that column. An uploaded column whose name matches a secret Variable is dropped **loudly** (named on screen as ignored and unstored) and **client-side** — those values never reach the backend.

INCOMPLETE ROWS — a row missing a value for a Variable is, by default, created as a `skipped` row on the Batch, NOT discarded. Reason: spec 9gea5p already has the `skipped` row status and `POST /api/batches/{id}/rows/{n}/rerun`, so an incomplete row stays visible in the batch table, gets filled later, and re-runs into the same Batch; discarding at creation is the only version that loses information. "Run them anyway" remains available, demoted to a checkbox rather than a co-equal choice, because an empty Variable can be legitimate when the Step referencing it is optional or disabled. Blocking creation outright was rejected for the same reason.

BEFORE COMMITTING — the sticky footer carries: the Batch name (default "{Workflow name} — {date}", or "… — rerun of {Batch}" when copied), total rows / complete / missing-a-value counts, the incomplete-row policy, and the sequential ETA ("N Runs, one at a time · about M min"). The POST is `POST /api/workflows/{id}/batches {name, rows:[{variables}]}` (spec 9gea5p) carrying non-secret values only.

REUSE — "copy rows from a past Batch" is a toolbar action that fills the grid; the rows are copied and owned by the new Batch (8iuuh8's no-saved-datasets rule holds). An existing Batch offers "start a new Batch from these rows".

VARIABLES CHANGED AFTER CREATION — detect and tell, nothing cleverer (pinning is out of scope, ds8zyn). On the creation page: a banner that the Workflow published a new Version declaring a new Variable, with "give every row the same value". On an already-running Batch: a banner naming how many QUEUED rows have no value for the new Variable, offering fill-the-queued-rows (one write), run-them-as-they-are, or cancel-the-rest. Succeeded and running rows are untouched.

FEEDS — the spec for the Batch-creation + Schedule-creation area.
