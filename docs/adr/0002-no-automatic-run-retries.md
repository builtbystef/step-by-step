# 0002 — No automatic Run retries

## Context

A Run may click buttons, submit forms, make purchases, or cause other effects on an external site. If a Run stops halfway through, the system may not know which effects already happened.

## Decision

Never retry a Run automatically. A Run that stops because of Worker loss, timeout, or Step failure becomes `failed` with a machine-readable Failure Reason. A user must choose to run it again.

Playwright may still retry safe checks inside one Step, such as waiting for an element to become usable.

## Reason

Repeating a non-idempotent action can be worse than asking a user to review and retry the Run.
