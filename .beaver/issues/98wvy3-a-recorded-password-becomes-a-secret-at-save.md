---
id: 98wvy3
title: A recorded password becomes a Secret at save
state: todo
priority: medium
depends_on:
    - jdgmdx
    - 7vuup5
parent: 54i6da
created: 2026-08-14T06:15:44Z
updated: 2026-08-14T06:15:44Z
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
