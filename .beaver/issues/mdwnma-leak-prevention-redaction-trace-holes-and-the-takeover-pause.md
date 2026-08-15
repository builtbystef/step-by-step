---
id: mdwnma
title: 'Leak prevention: redaction, trace holes, and the takeover pause'
state: todo
priority: medium
depends_on:
    - qf8loh
    - 1q7qp8
    - qmnvgr
    - tls69i
parent: 54i6da
created: 2026-08-14T06:16:25Z
updated: 2026-08-14T07:45:35Z
---

## What to build

The guarantees that a Run's own output can never disclose a credential. Redaction happens in the Worker, before anything is published to Redis: every secret value resolved for the Run — org values and Personal Overrides alike, the Worker redacts whatever plaintext it was handed — is substring-replaced with `••••` in log lines, error strings, and failure detail — with no minimum length, because a three-character secret shredding the user's own logs is a better failure than a three-character secret appearing in them. Playwright trace capture is bracketed around every secret-referencing Step (stop the chunk before, start a new one after): the trace has a hole, not a password. Screenshots are not suppressed — password fields mask themselves, and that is accepted. During a waiting-for-human interval the live stream continues (the user is watching themselves), but periodic screenshots and trace capture pause, resuming at hand-back — a screenshot must never catch an MFA code mid-type.

This slice's edge on the execution spec is an umbrella; tighten it when that spec is sliced.

## Acceptance criteria

- [ ] A log line containing a Run's secret value, published through the Worker helper, arrives over the SSE stream with `••••` and no fragment of the value.
- [ ] A two-character secret is redacted too.
- [ ] An error string embedding the secret is redacted the same way before publish.
- [ ] The trace of a Run with a secret-typing Step has no chunk covering that Step, and chunks exist before and after it.
- [ ] Between take-control and hand-back, no periodic screenshot and no trace chunk is produced; both resume afterwards; the live stream keeps flowing throughout.
- [ ] Step payloads and Step Results carry Variable names only: a sweep of the Run's stored rows and Artifacts for the secret value finds nothing.
