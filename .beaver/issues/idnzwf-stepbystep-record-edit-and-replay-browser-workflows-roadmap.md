---
id: idnzwf
title: 'stepbystep: record, edit, and replay browser workflows — roadmap'
state: in-progress
assignee: builtbystef
priority: high
labels:
    - roadmap
created: 2026-08-08T07:07:08Z
updated: 2026-08-10T05:13:11Z
---

## Goal

A user can install a Chrome extension, record actions they perform on a website (navigate, click, type, select, download, extract data) as a named workflow of editable semantic steps; edit that workflow in a web app; run it on demand, on a schedule, or as a batch over a list of input rows; watch runs live with the ability to take over when the site demands a human (CAPTCHA, MFA) and hand control back; and review each run's artifacts (screenshots, traces, downloads, extracted data).

Under the hood: Next.js/TypeScript frontend, FastAPI/Python backend, versioned workflows in PostgreSQL, Redis-queued executions on isolated Playwright workers, separate artifact storage, and securely handled auth state and secrets.

Related but outside this DAG: issue `ymz3md` (establish stack, checks, and dev commands) — the first implementation session lands it.

## Frontier

<!-- In-scope questions that are too vague to be nodes. They become nodes as the roadmap advances. -->

- Artifact storage: retention policy, linkage from runs and steps to artifacts. (The backend choice settled in px25yw: S3-compatible, MinIO in the compose stack, workers write directly.)
- Scheduling engine details: cron expression UX, timezones, missed-run and overlap policy. (The dispatch mechanism settled in px25yw: a backend scheduler loop scans Postgres each minute and enqueues due Runs.)
- Batch creation/management UI — prototype candidate. (The workflow editor UX became node 3iwv5i when the data model settled; the live run view became node apx4rs when the execution architecture settled.)
- Extracted data delivery: where a Run's assembled output object goes — view in UI, download, webhook, API. (The per-step schema settled in ds8zyn.)
- Saved reusable datasets (a list-of-rows entity that outlives one batch) — revisit when usage shows the reuse pattern; v1 batches own their rows (8iuuh8).
- Monorepo layout, local dev environment, deployment target and hosting. (The service list settled in px25yw: one docker compose stack — backend, Workers, Postgres, Redis, MinIO.)
- Observability: run logs, worker health, metrics. (px25yw gives the primitives: worker heartbeats on Run rows, log-line events over Redis pub/sub.)

## Out of scope

<!-- Items excluded on purpose. The list only grows. One line for each item, with the node's ref when it was one. An item never moves back in. -->

- Teams, sharing, and org roles — accounts are personal; multi-tenant means isolated users (8iuuh8).
- Hosted/paid SaaS offering — self-hosted open source now; hosted is a possible future (8iuuh8).
- Loop, conditional, and assertion step types inside a workflow (8iuuh8).
- Reusing a step's extracted output as a later step's input; computed/derived variables (8iuuh8).
- One-off "run at a specific time" scheduling and interval-since-last-run mode (8iuuh8).
- Parallel execution of runs within a batch — sequential only (8iuuh8).
- Notifications (email/push) for runs waiting on takeover or failed (8iuuh8).
- Secrets supplied via CSV / batch rows (8iuuh8).
- Browsers other than Chrome (Firefox/Safari extensions) (8iuuh8).
- Recording on mobile (8iuuh8).
- rrweb (or any session-replay library) as the source of recorded steps (f10wq3) — it emits no portable element identity, only session-local integer ids resolved inside its own rebuilt DOM. It remains a candidate for *viewing* a run, never for producing one.
- Self-healing selectors for v1: DOM-tree-comparison healing (Healenium-style) and automatic selector regeneration after a failure (f10wq3) — no first-party or peer-reviewed evidence validates any shipped self-healing product, and a ranked list of record-time-verified alternatives captures most of the benefit. Revisit only with run data showing what actually breaks.
- Weighted multi-locator voting at replay for v1 (f10wq3) — the 29.5% robustness gain was measured across five XPath generators on 2015-era apps, and voting can let converging broken locators out-vote correct ones. Ordered fallback over a ranked list is the v1 policy; `wljln8` confirms it.
- Pinning a Schedule or Batch to a specific Version (ds8zyn) — they always execute the latest published Version; pinning is addable later as an optional version pointer.
- Nested/hierarchical extraction records (ds8zyn) — an extract step yields a named scalar or a flat list of records with named fields.
- Dynamic per-run container spawning and worker autoscaling (px25yw) — a fixed pool of Worker containers; the backend never holds Docker-socket privileges. Concurrency scales by redeploying with more replicas.
- Automatic Run-level retries (px25yw; ADR 0002) — Runs act on external websites and replay is not idempotent. Retrying exists only inside a step.
- A reserved Worker pool for takeover-capable Runs (px25yw) — a waiting_for_human Run occupies a regular Worker slot until resume or timeout.
- Pure master-detail (IDE-style) and pure narrative-sentence editor layouts (3iwv5i) — the editor is the hybrid: an inline card list whose card summaries are the narrative sentences.

