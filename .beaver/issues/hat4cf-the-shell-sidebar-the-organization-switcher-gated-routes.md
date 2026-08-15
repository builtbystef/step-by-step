---
id: hat4cf
title: 'The shell: sidebar, the Organization switcher, gated routes, and Settings'
state: todo
priority: high
depends_on:
    - shurgk
    - k678bs
    - jrp1pq
    - 3nxs4k
    - x06w5q
parent: pc0t8s
created: 2026-08-14T05:54:51Z
updated: 2026-08-15T04:11:51Z
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
