---
id: u8q8p3
title: 'Spec: recording, editing, and storage'
state: done
assignee: claude
priority: high
labels:
    - roadmap:idnzwf
    - session:spec
depends_on:
    - 8iuuh8
    - f10wq3
    - ds8zyn
    - 1zg7o0
    - zm0rfq
    - wljln8
    - 3iwv5i
parent: idnzwf
created: 2026-08-08T08:57:50Z
updated: 2026-08-11T18:48:24Z
---

Write the spec for the recording + editing + storage area (session:spec). The area's nodes: v1 scope (8iuuh8), selector research (f10wq3), workflow data model (ds8zyn), MV3 capture research (1zg7o0), recording-extension prototype (zm0rfq), selector-mismatch replay policy (wljln8), editor UX prototype (3iwv5i).

Read those nodes' notes and linked artifacts (this area's only). Interview to close remaining gaps (grill-me), confirm with the user, then invoke the create-specification skill. Publish the spec issue with a blocking edge back to each node it covers.

The spec must carry the save-time validation rule from ds8zyn: reject any step array with duplicate step ids; mint fresh ids when duplicating a workflow.

## Notes

**claude** — 2026-08-11T18:48:20Z

Spec published as d8ux2s (Recording, editing, and storage of Workflows), with blocking edges to all seven covered nodes (8iuuh8, f10wq3, ds8zyn, 1zg7o0, zm0rfq, wljln8, 3iwv5i).

Gaps closed by interview (2026-08-11), all user-confirmed:
- RE-PICK: a re-pick session reuses the recording handshake scoped to one Step; the user navigates to the page themselves (no workflow replay); the editor shows old vs new candidate lists and the confirmed replacement edits the Draft only. Glossary entry 'Re-pick' added.
- SECRETS AT CAPTURE: password values never leave the content script; the Step lands with a needs-secret marker and the recording save screen refuses to finalize until each is bound to a secret Variable; backend rejects unresolved markers. Non-password literals convert to Variables in the editor.
- UNSUPPORTED STRUCTURES: closed shadow roots and uninjectable cross-origin frames are detected at capture, warned inline in plain non-technical language, recorded as well as possible, and permanently flagged (red editor badge, distinct from amber fragile).
- RESPONSE BODIES: dropped from v1 entirely — no CDP Network.getResponseBody, no filtering policy needed (added to root Out of scope).
- RECORDING PROTOCOL: app-first (Workflow created in app, recording targets its Draft; re-record replaces behind a confirm); backend mints a recording-scoped token (one user + one Draft, TTL 1 h); extension calls create/checkpoint/finalize directly; checkpoints make sessions survive service-worker death and token expiry (re-mint against the same session).
- Two confirmed inferences: Variable declarations snapshot with the Version (the Draft document holds steps + variables); dismissing the debugger infobar ends the recording, keeping captured Steps.

Seams (user-agreed): backend HTTP API (primary), recorder capture pipeline at the extension boundary (headless Chromium + unpacked extension), selector resolution module. Editor UI gets no automated seam.
