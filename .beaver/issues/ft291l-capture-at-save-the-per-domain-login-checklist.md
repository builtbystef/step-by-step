---
id: ft291l
title: 'Capture at save: the per-domain login checklist'
state: todo
priority: medium
depends_on:
    - gl1cnk
    - 7vuup5
parent: 54i6da
created: 2026-08-14T06:15:34Z
updated: 2026-08-15T04:32:52Z
---

## What to build

The consented capture of signed-in state at recording save. The save flow lists every distinct registrable domain the recording navigated to — no signed-in heuristic filters the list, because a session cannot be reliably detected from outside and a wrong filter silently hides the option the user wanted. Each row is an unchecked checkbox: "Save your login for example.com? Future runs will start already signed in." A checked row exposes a destination choice: **for the Organization** (the default) or **just for me** — the recording member's Personal Override. Where a record already exists at the chosen destination, the row adds "replaces the login saved on 3 Aug" (or "replaces your login saved on 3 Aug") and is still unchecked. Nothing is captured for an unchecked domain.

For a checked domain the extension captures cookies through `chrome.cookies` — including httpOnly, and each cookie's secure, sameSite, and partition key — plus localStorage and sessionStorage per origin, read by content scripts in the recorded frames (the service worker can reach neither storage). sessionStorage is included because some sites keep the access token there, and a login that transfers almost is the worst failure this feature has. Captures upload over the recording-scoped credential — the session knows its Workflow's Organization and its recording member, so `personal` needs no extra identity:

```
POST /api/recording-sessions/{sessionId}/auth-states
  { captures: [ { ...AuthStateBlob, scope: "organization"|"personal" } ] }  → 204
  // upsert per (domain, destination)
```

## Acceptance criteria

- [ ] A recording that navigated `www.example.co.uk`, `app.example.co.uk`, and `accounts.google.com` offers exactly two rows — `example.co.uk` and `google.com` — both unchecked, each defaulting to the Organization destination when checked.
- [ ] A domain with an existing record at the chosen destination shows the replaces hint with the saved date — switching the destination switches which record the hint reflects — and is still unchecked.
- [ ] Leaving every box unchecked captures nothing: no upload happens and no rows appear.
- [ ] A checked domain's stored blob contains an httpOnly cookie (invisible to page scripts) and per-origin localStorage and sessionStorage entries from the recorded frames.
- [ ] A cookie's partition key survives into the stored blob.
- [ ] One domain captured for the Organization and another just-for-me lands as an org row and a personal row for the recording member; re-capturing one at the same destination in a later recording replaces that row's content on the same row id with `created_at` unchanged, leaving the other layer untouched.
- [ ] The endpoint honors the recording-session credential rules: a foreign or finalized session's credential is rejected.
