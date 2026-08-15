---
id: k678bs
title: Sliding session expiry and sign-out-everywhere
state: todo
priority: medium
depends_on:
    - lac27w
parent: ufnuvx
created: 2026-08-14T05:45:16Z
updated: 2026-08-14T05:45:16Z
---

## What to build

Sessions live for up to 30 idle days: activity extends them, silence expires them, and the extension writes are capped so the store is touched at most once per hour per session. The user gains a "sign out everywhere" action that revokes every session at once. Revocation is row deletion.

## Acceptance criteria

- [ ] A request with a session last touched 29 days ago → succeeds and extends the session.
- [ ] A request with a session idle for 31 days → 401, and the session cannot be used again.
- [ ] Two authenticated requests one minute apart → exactly one last-seen write; a request more than an hour after the last touch writes again.
- [ ] Sign-out-everywhere → 204 and deletes all of the caller's sessions: a second device's cookie stops working, while another user's sessions are untouched.
- [ ] The signed-in web app offers "sign out everywhere", which lands the user back at the sign-in page.
- [ ] HTTP seam tests with a real Postgres cover the four worked examples above, controlling session timestamps rather than waiting.
