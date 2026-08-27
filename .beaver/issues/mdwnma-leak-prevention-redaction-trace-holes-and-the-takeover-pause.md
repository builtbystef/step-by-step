---
id: mdwnma
title: 'Leak prevention: redaction, trace holes, and the takeover pause'
state: done
assignee: agent
priority: medium
depends_on:
    - qf8loh
    - 1q7qp8
    - qmnvgr
    - tls69i
parent: 54i6da
created: 2026-08-14T06:16:25Z
updated: 2026-08-27T07:21:28Z
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

## Notes

**claude** — 2026-08-17T04:03:58Z

Precedence pin (mirrored on tls69i): during waiting/human/verifying phases the no-screenshot rule wins over tls69i's always-screenshot-on-failure — a Step failed by takeover_timeout or takeover_abandoned takes no failure screenshot. Leak prevention outranks diagnostics.

**agent** — 2026-08-27T06:45:07Z

Seams (AFK): (1) Worker publish helper driven directly — log lines, two-character secrets, and error/failure strings redacted before Redis; the parent spec's SSE assertion is an integration test of that same helper. (2) Worker executor against Playwright fixture pages for trace holes around secret-referencing Steps, takeover pause of tracing/screenshots with the live page still open, and a sweep of stored results/artifacts for the secret value. Failure-screenshot precedence during waiting/human/verifying is encoded on the executor; VNC itself is 5yu03g.

**agent** — 2026-08-27T07:21:28Z

Completed leak prevention.

Redaction lives in the Worker, before Redis or Postgres: RedactingStore wraps the ResultStore after credentials fetch and substring-replaces every handed plaintext (org or override) with •••• in log lines, error_message, failure_detail, and trace-zip text. No minimum length. Driven directly in fast tests; the parent-spec SSE assertion is apps/api/tests/integration/test_run_events.py::test_a_secret_in_a_log_line_arrives_over_sse_redacted.

TraceCapture brackets secret-referencing Steps (stop_chunk before, start_chunk after) and pauses for the whole waiting/human/verifying interval, resuming at hand-back. Screenshots of secret Steps are not suppressed. Failure screenshots are refused when automation is off (takeover_timeout / takeover_abandoned). The live page stays open during park.

Seams as noted: helper + SSE; executor against Playwright fixture pages (trace holes, takeover pause, sweep of results/artifacts).
