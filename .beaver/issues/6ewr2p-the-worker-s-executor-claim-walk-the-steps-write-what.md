---
id: 6ewr2p
title: 'The Worker''s executor: claim, walk the Steps, write what happened'
state: done
assignee: agent
priority: high
depends_on:
    - 423dg6
    - mwrkwp
    - xkfmw8
parent: 9gea5p
created: 2026-08-14T07:41:22Z
updated: 2026-08-24T09:21:29Z
---

## What to build

The heart of the system. The Worker `BRPOP`s the dispatch list and claims the Run with a conditional update (`queued` → `running`, stamping worker_id, VNC endpoint, started_at, heartbeat_at); a claim that updates zero rows means the Run was cancelled or taken, and the Worker drops it and pops again. Per Run it opens a fresh headed Chromium on its X display with a throwaway profile, then walks the Steps in order: skip a `disabled` Step; resolve the Target through the resolution module (ordered fallback, ambiguity rejected, the timeout is the retry budget); perform the action; write the Step Result with the matched candidate's rank — the Selector Drift signal. A test Run executes the stored Draft snapshot instead of a Version.

Failure of a non-optional Step stops the Run: executed Steps keep their results, every unreached Step gets a `skipped` Step Result — a Run's result count always equals its Step count — and the Run ends `failed` / `step_failed`. An `optional` Step whose target never appears is `skipped` and the Run continues. The Worker accumulates automation time; exceeding the Workflow's run timeout (default 30 minutes) at a Step boundary → `failed` / `run_timeout`. A browser that fails to open before Step 1 → `failed` / `startup_failed`. On terminal: nothing is assembled (output is derived on read), the browser closes, the profile directory is deleted, the terminal status is set.

Credentials and Auth State injection plug in through the 54i6da slices; until then the executor runs Versions without secret Variables. Tested at the executor seam: hand it a Version and local fixture pages, drive a real browser, assert on the rows, status, and intervals it writes.

## Acceptance criteria

- [ ] A three-Step Version over fixture pages → three `passed` Step Results in order, run `succeeded`, and one `automation` control interval covering the Run.
- [ ] A Step whose top candidate is gone but whose rank-2 candidate matches → `passed` with `matched_candidate_rank` = 2 and the candidate count recorded.
- [ ] A non-optional Step whose target never appears → that Step `failed`, every later Step `skipped`, run `failed` / `step_failed`; an `optional` Step in the same position → `skipped` and the Run continues to success.
- [ ] A `disabled` Step is skipped without touching the page.
- [ ] A test Run executes the Draft snapshot: a Draft that differs from the latest Version demonstrably drives the browser with the Draft's steps.
- [ ] Two enqueued Runs and one Worker → they execute one after the other; a duplicate id on the list is claimed once and dropped once.
- [ ] A Run cancelled between enqueue and claim → the claim updates zero rows and the Worker pops the next job.
- [ ] A Version exceeding the run timeout (fixture with a tiny timeout) → `failed` / `run_timeout` at a Step boundary, unreached Steps `skipped`.
- [ ] After a Run, no profile directory remains on the Worker.

## Notes

**agent** — 2026-08-24T09:08:59Z

Test seam selected from the parent spec: the Worker's executor against real Playwright fixture pages, with its Postgres writes and Redis claim queue observed at their public boundaries. This slice will exercise Version and Draft-snapshot Runs through the dispatch/executor entry points; selector resolution remains covered by its existing browser seam.

**agent** — 2026-08-24T09:21:29Z

Completed the Worker executor and dispatch loop. A Worker now BRPOPs the shared list, conditionally claims queued Runs with worker/VNC/start/heartbeat stamps, drops cancelled/stale/duplicate ids, selects the immutable Version or a test Run's Draft snapshot, and executes one fresh headed persistent Chromium context at a time. The executor writes ordered Step Results and one automation control interval durably, records selector rank/candidate count, skips disabled and optional-missing Steps, fails required misses and fills later skipped results, enforces the Run timeout at Step boundaries, interpolates Run Variables, closes the browser, removes the throwaway profile, then writes terminal status. Added browser-seam coverage for success, drift, required/optional failures, disabled behavior, Draft snapshots, serial/duplicate/cancelled dispatch, timeout, and profile cleanup; added a Postgres integration assertion for the conditional claim and snapshot selection. pnpm check, pnpm test, and pnpm test:browser pass. The new Postgres integration assertion was not runnable locally because the compose Postgres service was not running; the fast and browser tiers are green.
