---
id: 000gz2
title: 'Spec: secrets and auth state'
state: done
assignee: claude
labels:
    - roadmap:idnzwf
    - session:spec
depends_on:
    - 7o0nmx
    - u7nkwh
parent: idnzwf
created: 2026-08-11T19:45:17Z
updated: 2026-08-11T20:54:35Z
---

Write the spec for the secrets + auth state area (session:spec). The area's nodes: secrets and auth state storage/scoping/injection (7o0nmx, with ADR 0003), and reuse of Chrome-recorded auth state in a Playwright browser (u7nkwh).

Read those nodes' notes and linked artifacts (this area's only). Interview to close remaining gaps (grill-me), confirm with the user, then invoke the create-specification skill. Publish the spec issue with a blocking edge back to each node it covers.

Boundaries already fixed by neighbouring specs:

- The recording/editing/storage spec (d8ux2s) binds a `type` Step to a secret Variable by name only. This spec owns the Secret vault itself: storage, envelope encryption under the env-supplied master key (ADR 0003), vault UX, rotation, and the per-domain opt-in Auth State capture prompt at recording save.
- Injection into a Run's browser and write-back from a Worker are this spec's contract; the execution spec consumes it.

Out of scope, already settled on the root: cloud KMS integration, per-workflow secret values, per-domain locks or freshness stamps for Auth State write-back, suppressing screenshots on secret-referencing steps, silent Auth State export from the extension.

## Notes

**claude** — 2026-08-11T20:54:35Z

Spec published: `54i6da` — "Secrets and Auth State", with blocking edges back to 7o0nmx and u7nkwh.

The area's two nodes carried most of the ground already. This session closed the gaps that stopped an implementer, by interview (three rounds), and the answers are inside the spec. The ones that changed or extended what 7o0nmx settled:

- BINDING — "binds by name" (7o0nmx) is refined: the Variable's own name and the vault entry are separate, and the pointer is the Secret's **id** with the name cached for display. Reason: one flat per-user vault means identical Variable names would silently collide across Workflows, and an id pointer makes renaming a Secret free. `VariableBinding` in d8ux2s's Draft/Version document gains `secretId` and `secretName` (additive; not implemented yet).

- MASTER KEY LOCATION — Workers never receive `STEPBYSTEP_MASTER_KEY`. The key lives only in the backend; a Worker fetches its own Run's plaintext over an internal endpoint and writes Auth State back the same way. This is the "secrets boundary may be revisited" that px25yw flagged, resolved against its direct-Postgres default: Workers host hostile web content, so a compromised one gets the Runs it executes rather than every user's vault. To be recorded as **ADR 0004** with the first implementation slice. Workers keep direct Postgres access for everything else.

- REVEAL — the user overrode the write-only recommendation: values can be revealed on the secrets page. Two-stage — the account password opens a 5-minute reveal window on the session, each value re-masks after 30 s, `logout-all` closes it. Reason given: a deliberate reveal on a dedicated page is the user's own choice, and never appears in a Workflow. No reveal for Auth State.

- WRITE-BACK OF NEW DOMAINS — refresh-only stands, with one added path: at hand-back the Worker reports domains that gained a session and have no record, the run detail asks "keep this login for site.com?", and a consented domain joins the next write-back. Unanswered at Run end stores nothing — no pending blob anywhere. The Worker re-reads consents immediately before its final write-back, so an unconsented blob never leaves it, and the backend rejects (400) rather than silently drops one.

- INJECTION — all of the user's Auth State records load into every Run's context, not a subset computed from the Version's URLs: interpolated `{{variable}}` URLs and SSO redirects to identity-provider domains defeat static analysis exactly where it matters, and cookies stay origin-isolated inside a browser exclusive to that Run.

- Settled without controversy: registrable domain (eTLD+1) as the Auth State key; `sessionStorage` included in the blob (seeded by init script, since Playwright's storage state omits it); no TTL on records; capture prompt lists every navigated domain unchecked with no signed-in heuristic; PyNaCl SecretBox pinned, backend refuses to boot on a bad key; `rotate-master-key` CLI in v1, resumable after partial failure; redaction in the Worker with no minimum length.

- Two seams, agreed with the user: the backend HTTP API (redaction folded in — the Worker publish helper driven directly, asserted on the SSE stream), and the envelope-encryption module directly.

New dependency beyond PyNaCl: a public-suffix list, because eTLD+1 cannot be derived by string splitting.
