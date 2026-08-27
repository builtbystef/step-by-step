---
id: o99b7t
title: 'Deletion and removal reach the domain: Runs cancel, Artifacts purge, overrides die'
state: done
assignee: agent
priority: medium
depends_on:
    - x06w5q
    - jrp1pq
    - sl7h4j
    - 3679bv
    - gl1cnk
    - it3m03
    - g461z0
    - tls69i
    - 297ba3
    - qf8loh
parent: ufnuvx
created: 2026-08-14T05:46:32Z
updated: 2026-08-27T04:13:53Z
---

## What to build

The accounts spec's deletion and removal semantics, extended over the domain objects that now exist. Deleting an Organization first cancels its queued and running Runs (a Run acting with the Organization's Secrets must not outlive them), then purges everything it owns — Workflows, Drafts, Versions, Schedules, Batches, Runs, Step Results, Secrets, Auth State, Personal Overrides in Postgres, and the Runs' Artifacts in Garage. Removing a member (or a member leaving) deletes that member's Personal Overrides in the Organization's vault and nothing else: Schedules keep firing and Runs keep running, because domain work belongs to the Organization. Account deletion applies the removal semantics to every Membership it ends. Run cancellation mechanics are the execution spec's ground; this slice invokes them.

## Acceptance criteria

- [ ] Deleting an Organization with queued and running Runs cancels them before any purge begins.
- [ ] After the delete, none of the Organization's Workflows, Drafts, Versions, Schedules, Batches, Runs, Step Results, Secrets, Auth State, or Personal Overrides remain in Postgres, and the Runs' Artifacts are gone from Garage (verified by observing the object store).
- [ ] A delete with a wrong name confirmation still changes nothing, including in Garage.
- [ ] Removing a member deletes their Personal Overrides in that Organization; the shared org values still open, the Organization's Schedules keep firing, and a currently running Run finishes normally.
- [ ] A Run that is mid-flight when the Personal Overrides it resolved are deleted finishes with the credentials it already holds — removal does not cancel org work.
- [ ] Deleting an account removes that user's Personal Overrides in every Organization they belonged to, while those Organizations' work is untouched.
- [ ] Integration seam tests cover the full purge and both removal cases, observing external effects only.

## Notes

**claude** — 2026-08-17T04:03:58Z

Added blocking edge on qf8loh: the mid-flight-override AC observes credentials fetched once at Run start and held in Worker memory — behavior clxd1b/qf8loh land.

**agent** — 2026-08-27T03:53:20Z

Testing seam: the parent spec names HTTP against the FastAPI app with real Postgres. This slice's integration tests will drive Organization deletion, member removal/leaving, and account deletion through those HTTP routes; observe Garage through its S3 API; and use Worker-facing HTTP credentials plus the minute tick as the external domain seams for in-flight Runs and Schedules.

**agent** — 2026-08-27T04:13:53Z

Completed the deletion domain hooks. Organization deletion now locks and marks every live Run cancelled, commits that state before deleting any Garage object, signals running Workers, purges all Run Artifact objects, and then relies on the Organization cascades for the complete Postgres domain. Membership removal deletes that member's Secret Personal Overrides in the Organization; Auth State already follows the Membership cascade, and account deletion follows the user/Membership cascades across every Organization without touching org work. Integration coverage now populates Workflows, Drafts, Versions, Schedules, Batches, queued/running Runs, Secrets, both Auth State layers, Personal Overrides and Garage Artifacts; it also covers wrong confirmation, mid-flight resolved credentials, continued Runs/Schedules, and multi-Organization account removal. Verification: format/lint/typecheck passed; fast suite passed (497 Vitest, 55 API, 16 core, 10 Worker); full integration suite passed (318 tests).
