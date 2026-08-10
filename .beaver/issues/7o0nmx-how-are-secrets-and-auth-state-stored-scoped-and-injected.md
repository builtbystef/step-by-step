---
id: 7o0nmx
title: How are secrets and auth state stored, scoped, and injected without leaking?
state: done
assignee: claude
priority: medium
labels:
    - roadmap:idnzwf
    - session:grill
depends_on:
    - 8iuuh8
    - u7nkwh
parent: idnzwf
created: 2026-08-08T07:08:04Z
updated: 2026-08-10T18:44:35Z
---

One live interview (grill-me). With tenancy (8iuuh8) and auth-state transfer realities (u7nkwh) known, decide:

- What v1 stores: site credentials, exported session state, both? Encryption at rest (KMS? libsodium? app-level key) and key management for the chosen deployment shape.
- Scoping: secrets per workflow, per site, per user?
- Injection at run time: how a typed-password step references a secret, and how values are kept out of logs, traces, screenshots, and step payloads.
- Lifecycle: rotation, revocation, what happens on takeover when the user types a password into the worker browser.

## Notes

**claude** — 2026-08-10T18:44:23Z

Answers (interview 2026-08-10):

WHAT V1 STORES — Two distinct entities. (1) Secret: a named, encrypted value in a user-level vault; a Workflow's secret Variable binds to a Secret by name (one rotation point, reuse across workflows — values are NOT stored per workflow). (2) Auth State: a user's saved signed-in browser state (cookies + web storage) for one site, keyed by domain. They differ in lifecycle (passwords are stable; session state expires and is refreshed by Workers) and in consumption (typed into a field vs. injected into the browser context before first navigate). Both terms are in docs/GLOSSARY.md.

ENCRYPTION & KEYS — App-level envelope encryption: per-record data keys wrapped by a single 32-byte master key supplied via environment variable / compose secret (libsodium secretbox or Fernet). Postgres never sees plaintext. Losing the master key = stored values unrecoverable (documented, accepted). No cloud KMS in v1. Recorded as ADR docs/adr/0003-env-key-envelope-encryption.md.

SCOPING & INJECTION — Secrets: per user, in the vault; workflows bind by name. Auth State: per user per site (domain-keyed), injected automatically — before a Run starts, the Worker loads the user's Auth State for the domains the Version touches. No explicit "use session X" configuration on the workflow.

AUTH STATE CAPTURE — The extension exports cookies/web storage only via an explicit per-domain opt-in prompt at recording save ("Save your login for site.com?"). Never silent export.

AUTH STATE REUSE CYCLE — The Worker browser is ephemeral per Run; the Auth State store is the only cross-run carrier. Write-back happens at exactly two moments: when a Run succeeds, and when a takeover hands back (human-refreshed login persists even if the Run later fails). A failed Run never writes back — its state may be poisoned (bot challenge, half-login) and would overwrite a known-good session. Concurrent same-user same-domain runs: last-write-wins, accepted and documented; worst case is one extra login/takeover on the next run. No per-domain locks or freshness stamps in v1.

LEAK PREVENTION — A Secret's value never leaves the Worker in any queryable/stored form: step payloads and Step Results store the Variable name only; SSE log lines are redacted by substring match against the Run's secret values; Playwright trace capture is bracketed around secret-referencing steps (stop_chunk/start_chunk — the trace has a hole, not a password). Screenshots are NOT suppressed: password fields mask themselves, and that is accepted as sufficient (user decision — serious sites mask input).

TAKEOVER — During a waiting_for_human interval the live stream continues (the user watches themselves) but periodic screenshots and trace capture pause, resuming on hand-back; the interval appears in the timeline with no visual record (a screenshot must never catch an MFA code mid-type).

LIFECYCLE — Rotation: edit the Secret's value in the vault once; every bound workflow uses the new value on its next Run. Deleting a Secret: allowed with a warning listing referencing workflows; a Run whose bound Secret is missing fails at start with classified error missing_secret (no blocking deletes / zombie secrets). Deleting Auth State: plain per-site "forget this login" — future runs start signed out and may hit a login step or takeover; no cascade, no warning.
