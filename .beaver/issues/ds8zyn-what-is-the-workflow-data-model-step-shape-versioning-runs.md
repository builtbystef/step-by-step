---
id: ds8zyn
title: 'What is the workflow data model: step shape, versioning, runs?'
state: done
assignee: claude
priority: high
labels:
    - roadmap:idnzwf
    - session:grill
depends_on:
    - 8iuuh8
    - f10wq3
parent: idnzwf
created: 2026-08-08T07:08:04Z
updated: 2026-08-08T08:57:31Z
---

One live interview (grill-me). With v1 scope settled (8iuuh8) and selector strategy researched (f10wq3), decide:

- The semantic step: its data shape, per-type payloads, and how selectors (ranked lists? fallbacks?) live inside it.
- Workflow versioning: immutable versions vs. mutable draft + published; what a run pins to; edit semantics.
- The entity model: workflow, version, step, run, step-run, schedule, artifact-link — names go to `docs/GLOSSARY.md`.
- Extraction steps: how extracted values are declared and stored.

The answer gates the first spec area (recording + editing + storage).

## Notes

**claude** — 2026-08-08T08:56:51Z

Answers (interview 2026-08-08):

VERSIONING — Draft + publish. A Workflow has one mutable Draft that the recorder and editor modify; an explicit publish snapshots it as immutable, numbered Version N. Schedules, Batches, and on-demand runs execute published Versions. Rejected: version-per-save (history noise) and mutable-workflow-with-run-time-snapshot (loses version identity and rollback).

DRAFT TEST RUNS — The Draft can be run at any time; such a Run stores its own frozen snapshot of the Draft's steps instead of a Version pointer, and is flagged a test run in history. This keeps every Run's record immutable without minting noise Versions.

SCHEDULE/BATCH TARGETING — Schedules and Batches always execute the Workflow's latest published Version. No pinning to a specific Version in v1 (recorded under Out of scope; addable later as an optional version pointer on the schedule).

STEP SHAPE — Envelope common to all step types: id, type, position, user-editable label (auto-generated at record time, e.g. "Click 'Add to cart'"), optional flag (target never appears → skip the step, do not fail), timeout override (falls back to a workflow-level default), disabled toggle (stays in the workflow, does not execute). Per-type payload sits beside the envelope; element-targeting steps carry the ranked, record-time-verified selector candidate list from f10wq3.

STEP IDENTITY — Step ids are app-generated UUIDs minted when the step is created (recorder capture or editor add). Edits never rewrite existing ids; publish copies the Draft's array verbatim, so ids are stable across Versions. This enables cross-version step history: "failing since Tuesday", selector drift rank over the last N runs.

STEP STORAGE — Steps are a JSONB array on the Version row (and on the Draft): one self-contained document, copy-on-publish is a single insert, per-type payload changes need no migrations. Not per-step rows. Integrity is app-enforced, and the spec must state the rule: save-time validation rejects any step array with duplicate ids, and duplicating a workflow mints fresh ids. Versions are immutable, so a Step Result's (version id, step id) reference can never dangle.

RUN SIDE — A Run pins a Version (or embeds its draft snapshot) and owns Step Results: one row per executed step, with status (passed/failed/skipped), timing, which selector candidate matched (the drift signal from f10wq3), error message, artifact links, and any extracted value. Run statuses: pending → running → waiting-for-human → succeeded / failed / canceled, plus the test-run flag.

EXTRACTION — An extract step declares an output name. Scalar mode: one element, its text or an attribute, one named value. List mode: a repeating element yields a flat list of records with named fields, each field bound to a sub-selector within the repeating element. No nesting (Out of scope). The extracted value is stored as JSON on the step's Step Result; the Run exposes an assembled output object {output name → value} built from its Step Results, so a Batch of 50 rows yields 50 uniform output objects viewable as a table. Where the data then goes (UI view, download, webhook, API) stays on the Frontier.

PER-TYPE CALLS — wait: two modes, fixed duration or wait-until-element-appears (same ranked-selector target shape as other steps) with a timeout. pause-for-takeover: optional author-written instruction message shown to whoever takes over, plus an optional per-pause timeout override (falls back to the per-workflow default, ~30 min per 8iuuh8). Variable references: template interpolation with {{name}} placeholders inside string values (at minimum the type value and the navigate URL); literal text and variables mix freely; secret masking keys off the Variable's secret flag, not the syntax.

ENTITY MODEL — Glossary updated (docs/GLOSSARY.md): added Draft, Version, Step Result, Schedule, Artifact alongside the existing Workflow, Step, Run, Variable, Batch.
