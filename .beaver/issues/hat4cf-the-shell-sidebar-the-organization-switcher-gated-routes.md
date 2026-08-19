---
id: hat4cf
title: 'The shell: sidebar, the Organization switcher, gated routes, and Settings'
state: done
assignee: claude
priority: high
depends_on:
    - shurgk
    - k678bs
    - jrp1pq
    - 3nxs4k
    - x06w5q
parent: pc0t8s
created: 2026-08-14T05:54:51Z
updated: 2026-08-19T11:24:17Z
---

## What to build

The frame every signed-in screen renders inside. A persistent 216px left sidebar over a content column: the wordmark; the nav — Workflows, Runs, Schedules — a separator, Settings; a spacer; a footer holding the extension-pill slot and the user menu. The user menu also holds the Organization switcher: it names the active Organization, lists the user's others, and switching changes what every list shows — the fetch wrapper stamps the active Organization's header on every call, and the choice persists across reloads. There is no top bar and no dashboard: sign-in lands on the Workflows route, the page title is the first thing in the content column, and the attention band's slot sits above it (fed by a later slice). Settings is a left section nav beside one panel, and re-homes every screen the accounts slices built. The shell layout resolves the identity once through the gate before rendering any child.

## Acceptance criteria

- [ ] The sidebar renders top to bottom: wordmark; Workflows, Runs, Schedules; a separator; Settings; a spacer; a footer with the connection-pill slot and the user menu showing display name, email, the Organization switcher, and Sign out.
- [ ] Switching Organizations re-scopes the app: every subsequent API call carries the new Organization's header, the lists change accordingly, and the choice survives a reload; a user with one Organization sees its name without a switcher menu.
- [ ] At or below 1024px the sidebar collapses to a 60px icon rail with the count-badge slot still visible; labels return above 1024px; 880px is the narrowest supported width.
- [ ] The shell resolves the current identity once via the gate before rendering children: a signed-out visitor to any inner route lands on sign-in with `next` — never a shell with dead nav.
- [ ] Signing in lands on the Workflows route; the Runs and Schedules destinations route inside the shell (their lists arrive with later slices).
- [ ] Settings is a section nav beside one panel: Account, then an Organization group — General (rename; and for the owner: transfer ownership and the type-the-name delete), Members, Invitations — then Secrets, Saved logins, and Browser extension; the bare settings path redirects to Account.
- [ ] The Account section gathers the account controls in one panel: display name, sign out everywhere, and the type-the-email delete with its sole-owner explanation; the Organization sections re-home the members and invitations screens the accounts slices built; Secrets, Saved logins, and Browser extension render placeholder panels until their specs land.
- [ ] Role gating inside Settings: Members is visible to every role; Invitations and the management controls appear only for owners and admins; the owner-only controls (transfer, delete) appear only for the owner — and requesting a section a role cannot use redirects to Account.
- [ ] A pending-invitation banner surfaces in the shell when the current user has Invitations to accept.
- [ ] Sign out lives in the sidebar user menu, not in Settings.

## Notes

**claude** — 2026-08-19T11:24:17Z

Built the shell: `app/(shell)/` is the route group every signed-in screen renders inside, and `/signin` stays the one route outside it.

**Seams.** The spec's Testing Decisions name two, and only one of them is this slice's: `resolveGate` and its neighbours — pure functions, no DOM, no rendering stack (the spec refuses to add one for presentational code). So the tests are `lib/active-org.test.ts` (which Organization is active, and the choice that survives a reload), `lib/api.test.ts` (the `X-Organization` header and the `403 not_a_member` rule, at the shared client), `app/(shell)/nav.test.ts` (what the nav offers, and which address lights which item), `app/(shell)/settings/sections.test.ts` (the section nav per role, checked against `resolveGate` so the nav and the guard cannot disagree), and `app/(shell)/messages.test.ts`. No backend change: every route this slice needs already exists.

**What landed.**
- `shell.tsx` resolves `GET /api/auth/me` once and asks the gate before any child renders. The sidebar is shadcn's `Sidebar` at `collapsible="icon"`, 216px with a 60px rail; `open` follows a `(max-width: 1024px)` media query alone — deliberately no toggle, so the rail is always something the window width explains.
- `lib/active-org.ts` resolves the active Organization from the identity and the remembered choice (a Membership that ended cannot keep scoping the app) and holds the choice with its watchers. `lib/api.ts` gained two rules beside the 401 one: the header, read per request, and the lapsed-Membership rule, which reads the code from a clone so the screen still gets its refusal.
- Settings is a section nav beside one panel, and it re-homes the accounts slices' screens: `/account`, `/organization`, and `/invitations` are gone as top-level routes. The Organization sections act on the active Organization instead of iterating every Membership.
- Slots, not guesses: `slots.tsx` holds the attention band and the Runs count badge (`fkgat7`) and the connection pill (`20k5ft`). Nothing renders "not connected" before something has probed.

**Decisions a reviewer should see.**
- Transfer ownership moved from the member row to Settings → Organization → General, where the spec puts it, as a picker over the members `memberControls().makeOwner` already says are eligible. Members keeps the role change and the removal.
- The Account panel gained the display name (`PATCH /api/auth/me`) and kept sign out everywhere and the type-the-email delete. Plain sign out is in the sidebar user menu, not here.
- `globals.css` maps shadcn's `--sidebar-*` onto the existing palette rather than taking the CLI's values, so there is still one palette. The CLI also wrote `sheet`, `tooltip`, `separator`, `skeleton`, and `hooks/use-mobile.ts`, which `sidebar.tsx` imports.
- The nav item's tooltip is the browser's own `title` rather than a mounted `Tooltip`: in the rail the label is gone and the name has to come from somewhere that needs nothing around it.

**Verified in a real browser** (Playwright against the production build and a stub API, not committed — the spec refuses DOM tests): the sidebar renders in the specified order at 216px and collapses to exactly 60px at 900px; the switcher lists both Organizations and switching moved `X-Organization` onto the very next call and survived a reload; `/settings` redirected to `/settings/account`; as a member the nav dropped Invitations and asking for that address landed on Account; signed out, `/runs`, `/settings/organization/members`, and `/runs?status=failed` each landed on `/signin?next=…` with no shell drawn; the pending-invitation banner surfaced; no console errors.
