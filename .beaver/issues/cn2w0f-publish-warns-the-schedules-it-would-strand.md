---
id: cn2w0f
title: Publish warns the Schedules it would strand
state: todo
priority: medium
depends_on:
    - fpzupm
    - fq0wr7
parent: nno9gj
created: 2026-08-14T19:52:25Z
updated: 2026-08-14T19:52:25Z
---

## What to build

The publish action warns **before it acts** when the new Version declares a non-secret Variable that an existing Schedule of that Workflow has no value for: the confirmation names those Schedules and states that they will stop firing until their values are set. This is one of the three channels (with the table and the banner) that stand in for notifications, which v1 does not have. The slice carries whatever read the confirmation needs — the candidate Version's declared Variables checked against each Schedule's value set — plus the dialog line itself.

## Acceptance criteria

- [ ] Publishing a Draft that adds a non-secret Variable `region` while two Schedules of the Workflow lack a value for it → the publish confirmation names both Schedules and states they will stop firing until their values are set; confirming publishes, and both Schedules then read `needs_values`.
- [ ] Publishing a Draft that strands no Schedule shows the normal confirmation with no warning.
- [ ] Cancelling at the warning leaves the Draft unpublished and every Schedule untouched.
