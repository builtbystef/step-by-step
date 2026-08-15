---
id: shurgk
title: The sign-in screen, the route gate, the fetch wrapper, and the instance endpoint
state: todo
priority: high
depends_on:
    - 8cjj8g
    - lac27w
parent: pc0t8s
created: 2026-08-14T05:54:36Z
updated: 2026-08-15T04:11:51Z
---

## What to build

The screens outside the shell, and the guard logic that makes the rest of the app safe to render. A pure gate function decides, from the current identity and path, whether to render or where to redirect. A single global fetch wrapper turns auth failures into those same redirects — a tab left open across a session expiry recovers instead of rendering errors — and is the one place that will stamp the `X-Organization` header once the shell knows the active Organization. The unauthenticated instance endpoint (landed with the accounts tracer) tells the sign-in screen which copy to show. This replaces the minimal sign-in page the accounts slices landed, using the visual-language primitives: a centered 400px card under the wordmark, no sidebar, no attention band.

## Acceptance criteria

- [ ] The gate is one pure function over (identity, pathname) returning render-or-redirect, and direct tests (no browser, no DOM) cover the full table: signed-out on a work path → `/signin?next=<path+search>` (query encoded, e.g. `/runs?status=failed` round-trips); signed-out on `/signin` → render; signed-in on `/signin` → the Workflows list; otherwise render.
- [ ] `next` is honored only when it starts with a single `/` and is not an auth route; `https://evil.example/x` falls back to the Workflows list.
- [ ] Sign-in is one two-step screen for both new and returning visitors: step one takes the email ("Continue"); step two takes the 6-digit code, with distinct messages for a wrong code, an exhausted code (offering to send a new one), rate limiting, and — under invite-only — the `signup_closed` refusal, worded to say new accounts join by Invitation.
- [ ] With `signup_mode: "open"` the email step says an account is created if none exists; with `invite_only` it says sign-in only, new accounts by Invitation — both driven by the instance endpoint, never hardcoded.
- [ ] The global fetch wrapper turns any 401 into the sign-in redirect with `next`; every API call goes through it.
- [ ] Signing out clears the identity and lands on sign-in with no `next`.
- [ ] Seam tests: the gate's table and the `next` sanitization tested directly; the screen's states driven by the instance endpoint against a real Postgres.
