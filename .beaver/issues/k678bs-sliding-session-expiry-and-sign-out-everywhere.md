---
id: k678bs
title: Sliding session expiry and sign-out-everywhere
state: done
assignee: claude
priority: medium
depends_on:
    - lac27w
parent: ufnuvx
created: 2026-08-14T05:45:16Z
updated: 2026-08-19T01:09:05Z
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

## Notes

**claude** — 2026-08-19T01:09:02Z

DONE (2026-08-18). Sessions slide, expire, and can all be ended at once.

Backend — `accounts/sessions.py` and one new route:
- `SESSION_LIFETIME` (30 days) is now an IDLE limit, checked in `signed_in_user`: `now - last_seen_at >= 30 days` refuses with the same 401 `unauthenticated` every other not-signed-in case gets, and DELETES the row where it finds it. That deletion is the only sweeping the `sessions` table gets — there is no reaper job, and none is needed while every expired row is met by the request that would have used it.
- `TOUCH_INTERVAL` (1 hour) caps the extension writes: a request whose session was touched less than an hour ago writes nothing. The column measures silence in days, so an hour of resolution costs nothing and saves a row-write per read of every screen.
- The COOKIE slides with the row, which the acceptance criteria do not name but the behaviour needs: `set_cookie` carries `max_age=30 days`, so a browser told nothing more would drop it 30 days after SIGN-IN and leave a live session nobody could reach — activity would extend a session in the store that no browser could still present. It is re-stamped on the same schedule as the touch, through the `Response` FastAPI hands the dependency.
- `end_all(db, user)` deletes every session row of one user, behind `POST /api/auth/logout-all` (operation_id `signOutEverywhere`) → 204, cookie dropped. It takes the asking session with the rest deliberately: the action exists for a browser its owner no longer has, and keeping the current one would make it a lie on the one machine that can read it.

Frontend:
- `lib/identity.ts` gains `signOutEverywhereAndLeave`, which ends identically to `signOutAndLeave` — cache cleared, `/signin`, nothing carried — because the two are one action from where the visitor stands. The shared `letGo` is what makes "identically" a fact rather than a promise.
- `app/account/page.tsx` is a TEMPORARY HOME, the same way `app/invitations/page.tsx` is: it offers the one control this slice gives the account. Settings -> Account is where it belongs, and hat4cf (the shell) re-homes it — that issue's criteria already name "sign out everywhere" as an Account-panel control. Until the shell exists there is no Settings to put it in.

DECISIONS a reviewer should see:
1. `signed_in_user` COMMITS, which no other dependency in this app does. Both writes it can make — the slide and the reaping — are the session layer's own bookkeeping rather than the handler's work, and both have to survive an answer the handler then refuses to give. `docs/ARCHITECTURE.md`'s "Handlers commit for themselves" now carries this exception beside it.
2. An expired session is deleted rather than left refused. "Cannot be used again" holds either way; the deletion is what keeps the table from filling with rows nobody can use.
3. The cookie re-stamp reaches handlers that answer with a MODEL. FastAPI replaces the dependency's `Response` wholesale when a handler returns a `Response` of its own, and the two authenticated routes that do are `logout` and `logout-all` — both taking the cookie away rather than renewing it, so nothing is lost. Every read the app makes (`/api/auth/me` on each page load) answers with a model.

Tests — `apps/api/tests/integration/test_sessions.py`, HTTP against the app with a real Postgres, clock moved by a `travel` fixture rather than waited on. Six: 29 idle days still signed in and the request buys another thirty (proven at day 50); 31 idle days -> 401 and the row is gone; two requests a minute apart leave `last_seen_at` untouched while one 61 minutes later writes it; a sliding request hands back a fresh `Max-Age`; sign-out-everywhere -> 204 with a second device's cookie dead, the caller's replayed token dead, and another user's session untouched; and logout-all without a session -> 401. The `last_seen_at` reads are the file's one look into a table, and both claims they carry (a row's absence, and how OFTEN a column is written) are ones no HTTP answer can make — the two requests being counted both answer 200 either way. Frontend: two Vitest cases on `signOutEverywhereAndLeave` (where it lands, and that it calls `/api/auth/logout-all`).

`pnpm run ci` exit 0; `pnpm test:integration` 75 passed (69 before). OpenAPI schema and generated client regenerated and committed.
