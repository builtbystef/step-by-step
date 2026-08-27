---
id: 98wvy3
title: A recorded password becomes a Secret at save
state: done
assignee: agent
priority: medium
depends_on:
    - jdgmdx
    - 7vuup5
parent: 54i6da
created: 2026-08-14T06:15:44Z
updated: 2026-08-27T05:49:48Z
---

## What to build

The save-screen path that makes a just-recorded Workflow runnable without a second errand. Recording marked secret fields as needs-secret Variables and never let their values leave the content script (d8ux2s ground). At save, each needs-secret Variable prompts the user: create a new Secret — a name and the value — or pick an existing one from the vault. The save screen creates org Secrets only — a binding must point at one; a member who wants their own value sets a Personal Override afterwards in Settings. A new value goes straight to the backend over the recording-scoped credential and never enters the step buffer or the Draft document:

```
POST /api/recording-sessions/{sessionId}/secrets  {name, value} → 201 {id, name}
```

Either way, the resulting binding (`secretId`, cached `secretName`) is written into the Draft's Variable, so the first Run needs no further setup.

## Acceptance criteria

- [ ] A recording with a needs-secret Variable surfaces it at save; entering a name and value creates the Secret and binds the Variable — the saved Draft carries `secretId` and `secretName` and no fragment of the value.
- [ ] Picking an existing vault Secret binds without creating anything.
- [ ] A taken name surfaces the conflict (409 `name_taken`) on the save screen, and the user can rename or switch to picking the existing Secret.
- [ ] The created Secret lands in the Workflow's Organization's vault and appears in that Organization's Settings list like any other.
- [ ] The value travels in exactly one request — the recording-scoped secrets call: the checkpointed steps, the finalize payload, and the stored document contain none of it.
- [ ] The endpoint honors the recording-session credential rules: a foreign or finalized session's credential is rejected.

## Notes

**agent** — 2026-08-27T04:39:45Z

AFK test seams: (1) backend HTTP integration for the recording-scoped Secret create call, observing it through the Organization vault API and Draft finalization; this covers organization scope, name_taken, token/session/finalized refusals, and absence of plaintext from checkpoint/finalize/document. (2) the extension recording boundary in the browser harness for one create request followed by finalize, with the value absent from every other request; pure recording binding tests cover existing-vault selection and binding shape. Existing Secret identities travel with the app's pending-recording handoff, while only a new value uses the recording capability.

**agent** — 2026-08-27T05:49:48Z

Completed recorded-password → Secret binding at save.

POST /api/recording-sessions/{id}/secrets creates an Organization Secret through the recording capability (same create path as Settings). 409 name_taken, 401 foreign/expired token, and 409 recording_session_finalized are the refusals. The editor hands vault identities on the pending-recording message so the save screen can pick an existing Secret without another credential; only a new value uses the recording call. The extension create request is the only place the plaintext travels — checkpoints, finalize, and the stored Draft carry secretId/secretName only.

The save screen lists each needs-secret Step with a Variable name, a vault picker, and a create-new form. A taken name stays on the save screen with the conflict message so the user can rename or switch to the existing Secret.

Seams as noted: HTTP integration for create/list/reveal/finalize and token/session refusals; browser harness for one create then finalize (value absent elsewhere) and name_taken then pick-existing; bindSecretSteps for binding shape.

Verification: vp check; ruff/ty against the workspace venv; vp test (500); pytest fast; integration test_recording_sessions; extension browser tests. pnpm check/test Python fan-out cannot uv-sync in this sandbox.
