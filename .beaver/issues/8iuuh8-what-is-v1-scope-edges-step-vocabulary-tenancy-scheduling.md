---
id: 8iuuh8
title: What is v1? Scope edges, step vocabulary, tenancy, scheduling
state: done
assignee: claude
priority: high
labels:
    - roadmap:idnzwf
    - session:grill
parent: idnzwf
created: 2026-08-08T07:07:40Z
updated: 2026-08-08T07:52:59Z
---

One live interview (grill-me), limited to scope. Settle:

- Which step types ship in v1: navigate, click, type, select, download, extract — and which wait (variables/parameterization, loops, conditionals, assertions)?
- Single-user tool or multi-tenant with accounts? Teams/sharing?
- Scheduling: what granularity and features does v1 need (cron? intervals? one-off)?
- What is explicitly out of v1 (goes to the root issue's Out of scope list)?

The answers gate the data model, execution architecture, and secrets nodes. Seed `docs/GLOSSARY.md` with the terms this settles (workflow, step, run, etc.).

## Notes

**claude** — 2026-08-08T07:52:54Z

Answers (interview 2026-08-08):

TENANCY — Multi-tenant with personal accounts; every workflow, run, batch, and secret belongs to exactly one user. No teams, sharing, or org roles in v1. The product ships as self-hosted open source (an org may host one instance for its people); a hosted paid version is a possible future, not v1. Recorded as ADR docs/adr/0001-multi-tenant-self-hosted.md.

STEP VOCABULARY (v1) — navigate, click, type, select, download, extract, wait, pause-for-takeover. Deferred to post-v1: loop, conditional, and assertion step types.

VARIABLES — A workflow declares named variables, each plain or secret. Step values reference them by name: at minimum the `type` value and the `navigate` URL. Values arrive per run: entered manually for on-demand runs, per row in a batch, stored settings for scheduled runs. Secrets are stored encrypted and are never supplied via CSV/batch rows. Deferred: reusing a step's extracted output as a later step's input; computed/derived values.

SCHEDULING — On-demand runs plus cron-based schedules (presets — hourly, daily at a time, weekly — backed by a real timezone-aware cron expression). No one-off run-at-time scheduling and no interval-since-last-run mode. Missed-run and overlap policy stays on the Frontier.

BATCH (new v1 feature from this interview) — A batch is one workflow plus a list of input rows; each row supplies the workflow's variables and produces one ordinary run. Batch is a way of launching runs, not a step type (loops stay out of workflows). Rows come from CSV upload or an in-app grid editor; the batch owns its rows (no reusable dataset entity in v1 — duplicate-a-batch is the reuse path; saved datasets went to the Frontier). Runs in a batch execute sequentially. A failed run does not stop the remaining rows unless configured to.

UNATTENDED TAKEOVER — When a pause-for-takeover step fires with nobody watching, the run parks in a waiting-for-human state visible on the dashboard and fails after a per-workflow timeout (default ~30 minutes). No email/push notifications in v1.

Glossary seeded: Workflow, Step, Run, Variable, Batch (docs/GLOSSARY.md). Out of scope additions recorded on root idnzwf.
