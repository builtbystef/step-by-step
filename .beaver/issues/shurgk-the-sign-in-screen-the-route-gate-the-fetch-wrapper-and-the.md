---
id: shurgk
title: The sign-in screen, the route gate, the fetch wrapper, and the instance endpoint
state: done
assignee: claude
priority: high
depends_on:
    - 8cjj8g
    - lac27w
parent: pc0t8s
created: 2026-08-14T05:54:36Z
updated: 2026-08-18T10:08:05Z
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

## Notes

**claude** — 2026-08-18T10:08:01Z

Landed the sign-in screen, the route gate, and the global fetch wrapper. `pnpm run ci` green: 85 files formatted, no lint or type errors in 45, 43 Vitest and 44 pytest tests pass, the build has no OpenAPI/client drift.

WHAT IS THERE

- `apps/web/lib/gate.ts` — `resolveGate(me, activeOrgRole, pathname)`, pure: no router, no DOM, no fetch. The whole spec table, in order, with the rules as a doc comment above the function. `landingAfterSignIn(next)` is the other half: `next` is honored only when it is a path of this app and not an auth route, and otherwise falls back to `HOME_PATH`.
- `apps/web/lib/api.ts` — the fetch wrapper. One response interceptor on the client every generated call already shares, so "every API call goes through it" is true by construction rather than by discipline. `app/providers.tsx` installs it once.
- `apps/web/lib/identity.ts` — `IDENTITY_KEY`, `identityQuery()` (the shared `GET /api/auth/me`), and `signOutAndLeave`.
- `apps/web/app/signin/` — `page.tsx` (a Suspense boundary, because the screen reads `next` from the query), `sign-in-screen.tsx`, and `messages.ts`, which is where every sentence that depends on an answer is decided.
- `apps/web/app/page.tsx` — was the accounts tracer's minimal sign-in page; now a redirect to `HOME_PATH`.
- `packages/api-client/src/index.ts` re-exports the generated `client`. The hand-written entry, not the generated tree, so a regeneration does not drop it.
- shadcn's `input` and `label` generated into `components/ui/`. The CLI ran plainly and wrote nothing else.

DECISIONS A REVIEWER SHOULD SEE

1. THE 401 RULE IS THE GATE, NOT A SECOND COPY OF IT. A 401 means the visitor has no session, so the wrapper asks `resolveGate(null, null, <where they are>)` and follows its answer. That is what keeps `/signin` from redirecting to itself: `GET /api/auth/me` answers 401 there by design, and the gate says render. Verified by hand — a wrong code renders `bad_code` on the sign-in screen without navigating.

2. THE CACHE IS EMPTIED BEFORE THE REDIRECT, and the order is load-bearing. A cached identity would tell the sign-in screen the visitor is signed in and bounce them straight back to the screen that just answered 401.

3. `next` KEEPS ITS SLASHES. The spec's worked example is `/signin?next=/runs%3Fstatus%3Dfailed`, so the encoding is `encodeURIComponent` with `%2F` put back: a slash is legal in a query value, and it round-trips through `URLSearchParams` either way. Asserted both directions in `lib/gate.test.ts`.

4. THE GATE TAKES THE ROLE AND CARRIES THE INVITATIONS RULE, which is the spec's signature and table rather than this issue's shorter phrasing of it. It is pure and cheap, and the alternative is `hat4cf` changing the signature the moment it mounts the gate. Gating stops at the route; the owner-only controls inside `/settings/organization` hide by role, per the spec.

5. THE SCREEN'S COPY IS A MODULE, NOT JSX. The spec rules out component and DOM tests, so `app/signin/messages.ts` is where the four refusals and the two signup-mode notes are decided, and `messages.test.ts` asserts that no two refusals read alike. `code_exhausted` and `rate_limited` are `t7jki2`'s to send; this screen already tells them apart, which is what this issue's criterion asks for.

6. SIGN-OUT IS A FUNCTION HERE AND A MENU ITEM THERE. `signOutAndLeave` ends the session, empties the cache, and lands on `/signin` with nothing carried — `next` says "you were sent away from somewhere", and someone who signed out was not. The sidebar user menu that calls it is `hat4cf`'s, by its own criterion.

VERIFIED BY HAND, in Chrome against the running stack (real Postgres, console mailer), because the spec rules out DOM tests: the two email-step notes under `SIGNUP_MODE=open` and `invite_only`, both read from `GET /api/instance`; sign-up through both steps for a new address; the `bad_code` refusal; the `signup_closed` refusal with its Invitation wording under invite-only; "Use a different email" returning to step one with the refusal cleared; a signed-in visitor at `/signin` redirected away; `/signin?next=/runs%3Fstatus%3Dfailed` landing on `/runs?status=failed`; and `next=https://evil.example/x` falling back to `/workflows`.

WHAT A REVIEWER WILL MEET: `/workflows` IS A 404 UNTIL `hat4cf` AND `5rkj33` LAND. Signing in lands there, as the spec says it must, and the shell that renders it comes next. Nothing was stubbed in its place: the list and the shell are those slices' work, and a placeholder would be deleted by them.

DOCS: `docs/ARCHITECTURE.md`'s frontend data-layer section now names the three modules and the seam they sit on.
