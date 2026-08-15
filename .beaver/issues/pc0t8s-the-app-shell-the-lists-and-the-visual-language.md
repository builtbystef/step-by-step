---
id: pc0t8s
title: The app shell, the lists, and the visual language
state: todo
labels:
    - spec
depends_on:
    - dm4cff
    - 7mfxzj
created: 2026-08-12T05:15:43Z
updated: 2026-08-15T04:13:45Z
---

# The app shell, the lists, and the visual language

## Problem Statement

Five published specs describe deep surfaces — the editor (`d8ux2s`), the vault (`54i6da`), the run detail and batch progress (`9gea5p`), Batch and Schedule creation (`nno9gj`), accounts (`ufnuvx`) — and every one of them assumes a frame that none of them describes. Concretely, five things are missing:

1. **There is nowhere to land.** After sign-in no screen exists, no list renders the Workflows a user owns, and the run detail `9gea5p` specifies is reached from a Runs list that nothing draws.
2. **A user cannot learn that a Run is waiting for them** unless they already have that Run open — SSE is per-Run and per-Batch only (`9gea5p`), and `8iuuh8` ruled out notifications. Meanwhile the takeover deadline is real: 30 minutes by default, and passing it fails the Run with `takeover_timeout`. An unattended pause silently burns its budget.
3. **The sign-in screen has no home**, and a shell rendered naively over an expired session or a Membership that ended mid-tab is a wall of errors with dead nav.
4. **Nothing renders a Workflow.** No published spec defines a list, create, rename, delete, or duplicate route for Workflows — `d8ux2s` specifies Draft and Version *behavior* and lists only the recording-session routes.
5. **The vocabulary is undefined.** All five specs use words like "status chip", "amber callout", "locked column" and "hatched occurrence" with nothing behind them. Without a definition the first implementation session invents one by accident and every later session inherits it.

## Solution

The frame, and nothing else. A persistent left sidebar with exactly three primary destinations — Workflows, Runs, Schedules — plus Settings beneath a separator. No dashboard: sign-in lands on Workflows, and the promise that a waiting Run is visible everywhere is kept by the shell itself, through an amber attention band across the content column and a count badge on the Runs nav item, both fed by one small polled endpoint.

Runs history and Schedules are each **one** component: the global screen and the Workflow's tab are the same file with an optional `workflowId` prop. A Workflow has a detail page with four tabs — Editor, Runs, Schedules, Batches. The two-step sign-in screen (email → Sign-in Code) sits fully outside the shell, and a pure resolver decides, from the current identity and path, whether to render or where to redirect — so an expired session is a single redirect rather than a wall of 401s. An instance with no Workflows and no extension shows a two-step first-run panel, because `n52g83` made installation unpacked and manual.

Underneath it all, a named visual language: five semantic hues with one meaning each, a six-size type scale, and eleven primitives with rules, most of them mapped onto shadcn/ui components and the rest built here because the library has no equivalent.

## User Stories

1. As a signed-in user, I want to land on my Workflows, so that the first thing I see is my own work rather than a summary of it.
2. As a user with a Run paused for a CAPTCHA, I want every screen to tell me it is waiting and how long I have left, so that the takeover deadline does not pass while I am on another page.
3. As a user, I want the Runs nav item to carry a count of what is in flight, so that I know something is happening without opening a list.
4. As a user, I want one reverse-chronological Runs list, filterable by status and trigger, so that "what happened lately, and what is running now?" has one answer.
5. As a user on a Workflow, I want its Runs and Schedules tabs to be the same lists filtered to it, so that per-Workflow history is not a filter dance and never disagrees with the global view.
6. As a user with forty Workflows, I want a search box and a sort control, so that finding one is a keystroke rather than a scroll.
7. As a user, I want to create, rename, duplicate, and delete a Workflow from its list row, so that housekeeping does not require opening the editor.
8. As a user whose Workflow has never been published, I want every Run, Batch, and Schedule action to be disabled behind the same one sentence, so that the reason is unambiguous wherever I meet it.
9. As a new user of a fresh instance, I want the Workflows screen to walk me through installing and connecting the extension, so that the manual install is a guided step rather than a dead end.
10. As a member of several Organizations, I want a switcher in the shell that re-scopes every list, so that where I am working is always explicit.
11. As a visitor to an invite-only instance, I want the sign-in screen to say plainly that new accounts join by Invitation, so that I am not left guessing after a refused code.
12. As an org owner or admin, I want members and Invitations inside Settings, so that on a one-person Organization they are one section of one screen rather than a destination competing for attention.
13. As an implementer of a later spec, I want the status chip, the callout, and the other named primitives to exist already, so that I inherit the vocabulary instead of inventing a second one.

## Implementation Decisions

### The shell

A persistent left sidebar, 216px wide, over a content column. Top to bottom: the wordmark; the nav — Workflows, Runs, Schedules — a separator, then Settings; a spacer; and a footer holding the extension connection pill and the user menu (display name, email, the Organization switcher, Sign out). The switcher names the active Organization and lists the user's others; switching re-scopes every list, and the choice persists across reloads. A user with one Organization sees its name without a menu.

- **The attention band spans the content column**, directly under the top of the main area and above the page title. This is variant A of `7mfxzj`, chosen over the band inside the sidebar (it can name only one Run and costs sidebar height) and a pill in a persistent top bar (the quietest of the three, which is wrong for the one signal whose reason to exist is a deadline that fails the Run).
- **There is no top bar.** The page title is the first thing in the content column.
- **At ≤1024px the sidebar collapses to a 60px icon rail**, keeping the count badge visible. Labels return above 1024px. 880px is the narrowest width this spec supports.
- **The count badge on the Runs nav item** shows `running_count + queued_count + waiting_count`, hidden at zero, amber when `waiting_count > 0` and blue otherwise.
- **The Organization sections live inside Settings**, not beside the work. On a one-person Organization they are then one section of one screen, and still one click from anywhere.

### Routes and guards

One route sits outside the shell. Every other route renders inside it.

```
OUTSIDE THE SHELL — no sidebar, no attention band
  /signin                       the unauthenticated landing: email, then the Sign-in Code

INSIDE THE SHELL
  /workflows                          the list, or the first-run panel
  /workflows/[id]                     → redirects to /workflows/[id]/editor
  /workflows/[id]/editor              d8ux2s
  /workflows/[id]/runs                <RunsList workflowId>
  /workflows/[id]/schedules           <SchedulesList workflowId>
  /workflows/[id]/batches             the Workflow's Batches (nno9gj)
  /runs                               <RunsList />
  /runs/[id]                          the cockpit (9gea5p)
  /batches/[id]                       batch progress (9gea5p)
  /schedules                          <SchedulesList />
  /settings                           → redirects to /settings/account
  /settings/account                   ufnuvx
  /settings/organization              general: rename; owner: transfer, delete (ufnuvx)
  /settings/organization/members      every role sees; owner/admin manage (ufnuvx)
  /settings/organization/invitations  owner and admin only (ufnuvx)
  /settings/secrets                   54i6da
  /settings/logins                    54i6da — Saved logins
  /settings/extension                 install, connect, versions
```

Batch progress is a flat `/batches/[id]` rather than a segment under its Workflow, because a Run's `batch_row` backlink (`9gea5p`) carries only the batch id. Refusing a global Batches *index* (`nno9gj`) does not refuse a batch detail route.

**The gate is one pure function**, called by the shell layout with the resolved identity, the active-Organization role, and the current path, and by the sign-in page with the same inputs:

```ts
type Me = {
  id: string; email: string; display_name: string;
  orgs: { id: string; name: string; role: 'owner' | 'admin' | 'member' }[];
} | null;                         // null = no session

type Gate = { kind: 'render' } | { kind: 'redirect'; to: string };

function resolveGate(me: Me, activeOrgRole: 'owner' | 'admin' | 'member' | null, pathname: string): Gate;
```

Its rules, in order:

| Condition | Result |
| --- | --- |
| `me === null` and path is `/signin` | render |
| `me === null` | redirect `/signin?next=<pathname+search>` |
| path is `/signin` | redirect `/workflows` |
| path is `/settings/organization/invitations` and role is `member` | redirect `/settings/account` |
| otherwise | render |

(The owner-only controls inside `/settings/organization` hide by role rather than gating the route — the general section still renders rename-as-read-only facts for a member.) The shell layout resolves `GET /api/auth/me` once before rendering any child, so a signed-out user never sees a nav item they cannot use. **One global fetch wrapper** wraps every `/api/*` call: it stamps the active Organization's `X-Organization` header, turns a `401` into the `/signin?next=…` redirect, and turns a `403 code=not_a_member` into clearing the active-Organization choice and re-resolving — so a tab left open across a session expiry or a removal from the Organization recovers instead of rendering errors.

`next` is honored only when it starts with a single `/` and does not name an auth route; anything else falls back to `/workflows`. Signing out clears the identity and navigates to `/signin` with no `next`.

### The attention endpoint

`dm4cff` opened this endpoint as an additive touch to `9gea5p` because nothing in v1 can feed a shell-level indicator. Its contract:

```
GET /api/attention → 200
{
  waiting: [                       // at most 5, soonest deadline_at first
    { run_id, workflow_id, workflow_name, deadline_at }
  ],
  waiting_count: number,           // the true total, not the capped length
  running_count: number,
  queued_count: number
}
```

- **Polling**: a TanStack Query with `refetchInterval: 10_000` gated on `document.visibilityState === 'visible'` and `refetchOnWindowFocus`, so the poll stops on a hidden tab and catches up the moment the tab returns. It is never mounted outside the shell. Its key, `['attention']`, is **invalidated** rather than re-polled after any action that can change it — starting a Run, cancelling one, handing back control — and when a run detail's SSE stream reports a transition into or out of `waiting_for_human`. Those same actions invalidate the Runs list key, so the two never disagree.
- **The countdown is client-side**, computed from `deadline_at`, so the 10 s poll never makes the timer coarse. When a countdown reaches zero the band reads "the deadline has passed" and the next poll clears it — the reaper (`9gea5p`) is what actually flips the Run to `takeover_timeout`, and the client never asserts an outcome it did not observe.
- **Cost is independent of Run history.** The query touches only non-terminal Runs of the active Organization (the `X-Organization` header, like every org-scoped route), behind a partial index:

```sql
CREATE INDEX runs_attention ON runs (org_id, deadline_at)
  WHERE status IN ('queued', 'running', 'waiting_for_human');
```

  An instance with 50 000 terminal Runs and 3 non-terminal ones scans 3 index entries. The three counts come from the same index scan, so one round trip serves the whole shell.

**The band's wording** follows the count: one waiting Run names it — *"**Invoice download — AcmeBank** is waiting for you"* — and more than one reads *"**3 Runs** are waiting for you — the soonest is **Invoice download — AcmeBank**"*. The countdown is the soonest `deadline_at`. The action is **Take control**, navigating to `/runs/{run_id}`.

### The Workflows list, and the Workflow CRUD contract

No published spec defines these routes and this screen calls them, so this spec defines them, additive to `d8ux2s`, which keeps every Draft and Version behavior it already owns.

```
GET    /api/workflows?q=&sort=activity|name|created&limit=&cursor=
                                          → 200 [WorkflowSummary]
POST   /api/workflows        {name}       → 201 {id}
PATCH  /api/workflows/{id}   {name}       → 200 {id, name}
DELETE /api/workflows/{id}                → 204   (cascade: Drafts, Versions,
                                                   Schedules, Batches, Runs,
                                                   Step Results, Artifacts)
POST   /api/workflows/{id}/duplicate      → 201 {id}   (fresh Step ids, d8ux2s)
                                            409 code=run_active   (DELETE only)
```

```ts
type WorkflowSummary = {
  id: string;
  name: string;
  created_at: string;
  last_activity_at: string;        // the sort key: the latest Run's created_at,
                                   // else the Workflow's updated_at
  draft_state: 'never_published' | 'unpublished_changes' | 'in_sync';
  published_version?: number;      // absent when never_published
  last_run?: { id: string; status: RunStatus; finished_at: string | null };
  schedule_count: number;
  schedule_label?: string;         // "weekdays 09:00" when schedule_count === 1
  recent_run_median_ms?: number;   // nno9gj already asked d8ux2s for this
};
```

- `q` is a case-insensitive substring match on the name. `sort` defaults to `activity`. The cursor is keyset on `(sort key, id)`, so paging is stable while Runs are finishing underneath.
- **The search box and sort control render only at 40 rows or more** (`7mfxzj`); the endpoint always supports them.
- **The row**: name as primary; a meta line carrying the last Run's status chip and its relative time (or "never run") and the schedule indicator (`schedule_label`, or "3 schedules"); the `draft_state` badge on the right — neutral "not published yet", amber "unpublished changes", green "in sync with v4", reusing the chip `d8ux2s` already defines for the editor header; then hover actions.
- **Row click** opens `/workflows/{id}/editor`.
- **Actions**: an inline **Run**, and an overflow with New batch, New schedule, Duplicate, Rename, Delete.
- **Inline Run** starts a Run immediately and navigates to `/runs/{id}` when the Workflow declares no Variables. When it declares some, it opens the one-row value grid `nno9gj` already specifies for Schedules — including the locked cell for secret Variables — and starts the Run from there.
- **`never_published` disables Run, New batch, and New schedule** behind the one shared sentence (below), which is also what a `409 no_published_version` renders as.
- **Delete** is a confirm dialog that names what goes with it ("3 Schedules and 42 Runs will be deleted"). It is not type-to-confirm — that ceremony is reserved for account deletion (`ufnuvx`) — and it is refused with `409 run_active` while a Run of the Workflow is non-terminal.
- **New workflow** is a primary button opening a name-only dialog, because `d8ux2s`'s recording protocol is app-first: the Workflow is created and named in the app, and recording then targets its Draft. It lands on the empty Editor tab.

### The shared lists

`dm4cff` and `nno9gj` both ruled that the global list and the on-a-Workflow list are one component. The contract that keeps it that way:

```tsx
<RunsList />                        // /runs
<RunsList workflowId={id} />        // Workflow ▸ Runs

<SchedulesList />                   // /schedules
<SchedulesList workflowId={id} />   // Workflow ▸ Schedules

type ListProps = { workflowId?: string };
```

`workflowId` is the **only** prop, and it changes exactly three things: it adds `?workflow_id=` to the request, it hides the Workflow column, and it swaps the empty state for the Workflow's own call to action. Everything else is identical. **If a second file renders Run rows or Schedule rows, this rule is broken** — that is the reviewable form of the decision.

Both sit on one shared hook, a thin wrapper over TanStack Query's `useInfiniteQuery`:

```ts
function useCursorList<T>(opts: {
  path: string;                     // '/api/runs' | '/api/schedules'
  filters: Record<string, string>;  // reflected into the URL query
}): {
  items: T[]; loading: boolean; hasMore: boolean;
  loadMore(): void; refresh(): void;
};
```

The wrapper owns page size, the cursor-to-`pageParam` mapping, **Load more**, and mirroring filter state into the URL so a filtered list is linkable and survives a reload. The query key is `[path, filters]`, which is also what a mutation invalidates.

**The Runs list**, over `GET /api/runs?workflow_id=&status=&limit=&cursor=` (`9gea5p`): columns are status chip, Workflow, trigger, started (relative), duration, the Run id in monospace, and a right-hand cell that is a **Take control** button for a `waiting_for_human` Run and a chevron otherwise. Filters are status and trigger (`manual | schedule | batch | test`). **Rows navigate** to `/runs/{id}` rather than expanding — the cockpit is a full screen with a live browser pane, so expand-in-place does not fit it. Sort is reverse-chronological and is not user-controllable.

The list renders what `RunSummary` carries; the fields this screen needs are `{ id, workflow_id, workflow_name, status, trigger, created_at, started_at, finished_at, duration_ms, batch_id?, schedule_id? }`, alongside the `variables` `nno9gj` already added.

**The Schedules list** is `nno9gj`'s table, unchanged: columns are the enabled toggle, Workflow, recurrence in words with cron and timezone beneath, next due, last Run outcome, and the note column carrying the most recent non-firing Occurrence — with rows expanding in place. This spec adds only the `workflowId` contract above.

### The Workflow page

Header: the Workflow name, the `draft_state` chip, a **Run** action available from every tab, and an overflow repeating the list row's actions. Beneath it, four tabs, each its own URL segment so a tab is linkable and the back button works: **Editor** (default), **Runs**, **Schedules**, **Batches**.

The Batches tab lists the Workflow's Batches over `GET /api/batches?workflow_id=` (`nno9gj`), rows navigating to `/batches/{id}`. This is the only home for that list, now that a global Batches index is refused.

### Settings

A left section nav beside one panel. Sections: **Account** (`ufnuvx` — display name, sign out everywhere, the type-the-email delete with its sole-owner explanation), then an **Organization** group — **General** (rename; and, owner only, transfer ownership and the type-the-name delete), **Members** (every role sees the list; owners and admins manage roles and removal), **Invitations** (owner and admin only) — then **Secrets** (`54i6da`), **Saved logins** (`54i6da`), and **Browser extension**. Sign out itself is in the sidebar user menu, not here.

### The sign-in screen

One screen, no sidebar, no attention band, a centered 400px card under the wordmark. There are no passwords, so signing in and signing up are the same two steps (`ufnuvx`):

- **Step one** — email and one **Continue** button. Under `signup_mode: "open"` a grey line says an account is created if none exists; under `invite_only` it says sign-in only — new accounts join by Invitation. The copy is driven by `GET /api/instance` (`ufnuvx`, unauthenticated), never hardcoded.
- **Step two** — the 6-digit Sign-in Code, with distinct messages for a wrong code, an exhausted code (offering to send a new one), rate limiting, and — invite-only, no pending Invitation — the `signup_closed` refusal, worded to say new accounts join by Invitation. A **use a different email** action returns to step one.

After sign-in, a pending-invitation banner in the shell offers any Invitations waiting on the account.

### Empty and first-run states

- **Zero users** — nothing special: the first visitor signs in at `/signin`, and verifying the code creates the account and its Organization (`ufnuvx`).
- **No Workflows** — the Workflows screen *is* a first-run panel of two numbered steps. Step 1, **Install the browser extension**: the download (`GET /extension.zip`, `d8ux2s`), the unzip → `chrome://extensions` → Developer mode → Load unpacked sequence, and connecting by entering this instance's address in the extension popup — showing its live connection state and staying visible until the extension connects, then collapsing to a green tick. Step 2, **Create your first workflow**, always available, because naming a Workflow does not need the extension.
- **A Workflow with no Steps** — the editor's empty state, "Record your first steps", with Start recording disabled and replaced by the install/connect prompt when the extension is not connected.
- **A Workflow with Steps but no Version** — Run, New batch, and New schedule disabled everywhere behind **one identical sentence**: *"Publish a Version before this Workflow can run."* Used on the list row, the Workflow header, both creation pages, and as the rendering of a `409 no_published_version`.
- **A Workflow with no Runs** — the Runs tab offers Run; the Schedules tab offers New schedule.
- **Global Runs empty** — "Nothing has run yet / Runs appear here whether you start them by hand, on a schedule, or as a batch." → Go to Workflows.
- **Global Schedules empty** — "Nothing runs on a clock yet / A Schedule fires a published Workflow on a recurrence you choose, with a value set it owns." → Go to Workflows.
- **A filter or search matching nothing** is a one-line message inside the table, never the empty state — the difference between "you have none" and "none match" is the difference between two different next actions.

### The extension connection pill

A pill in the sidebar footer with three states — **connected · v1.2** (green), **not connected** (grey), **out of date** (amber) — and `/settings/extension` as its full surface: download, install steps, connect instructions, current and minimum versions.

How the app knows: `d8ux2s`'s connect flow has the extension inject its content script into the connected origin, so the page probes for a handshake message carrying the extension's version and treats silence for 1500 ms as "not connected", re-probing on focus. The version is compared against `GET /api/extension/version` → `{ current, minimum_supported }` (unauthenticated, `d8ux2s`); below the minimum is "out of date", and recording is blocked.

**The precision an implementer needs**: "not installed" and "installed but not pointed at this instance" are indistinguishable from the app's side. They must render as **one state with one recovery path**, and the Settings copy says so plainly rather than guessing.

### The visual language — foundations

Four foundations, from `7mfxzj`, evidenced by prototype branch `prototype/app-shell` (file `PROTOTYPE-app-shell.html`, LANGUAGE tab).

**1. Surfaces and ink.** `--bg #f5f6f8`, `--panel #ffffff`, `--ink #1a2130`, `--mut #68738a`, `--line #e3e7ee`.

**2. The semantic ramp — one hue, one meaning.** This is the rule the whole language rests on:

| Token | Value | Means |
| --- | --- | --- |
| `--accent` / `--accent-bg` | `#2f6fed` / `#e8effd` | the machine is acting; informational; interactive |
| `--wait` / `--wait-bg` | `#b97a08` / `#fdf3e0` | a human is needed, or was |
| `--human` / `--human-bg` | `#7c3aed` / `#f1eafd` | a secret, or a human-supplied value |
| `--ok` / `--ok-bg` | `#178a50` / `#e2f5ea` | succeeded |
| `--bad` / `--bad-bg` | `#c92f34` / `#fbe9e9` | failed |

shadcn ships only `--destructive`, so **the ramp has no library equivalent** — `--wait`, `--human`, and `--ok` are additions to the theme, and the one-hue-one-meaning rule is this spec's to enforce, not the library's.

**3. Type scale**, six sizes: 11px micro (badges, column headers, section labels), 12px small (meta lines, secondary controls), 13px (table cells, callout text — the half-step down), 14px body (`system-ui`, line-height 1.45), 16px title (panel and card titles), 20px/700 page (one per screen). **Monospace only for machine strings** — selectors, cron expressions, ids, countdowns.

**4. Spacing and radius.** Spacing 4 / 6 / 8 / 12 / 16 / 24. Radius 6 controls, 8 callouts, 10 cards, 999 pills. These are Tailwind's defaults (1 / 1.5 / 2 / 3 / 4 / 6), so they need no custom scale.

The theme tokens map onto shadcn's: `--bg → --background`, `--panel → --card`, `--ink → --foreground`, `--mut → --muted-foreground`, `--line → --border`, `--accent → --primary`.

### The visual language — the eleven primitives

Each is the **only** place its idea is rendered.

1. **StatusChip** — a lifecycle state, pill-shaped, 12px/600. Live states (`running`, `waiting_for_human`) carry a leading dot; `running` pulses. Palette: grey for `queued`/`cancelled`/`cancelling`/`skipped`/`missed`/`paused`, `--accent` for `running`, `--wait` for `waiting_for_human`, `--ok` for `succeeded`, `--bad` for `failed`. It renders Runs, Occurrences, and Batch rows alike.
2. **AttributeBadge** — rectangular, 11px/600, radius 5. A **property**, never a lifecycle state: selector health, `draft_state`, a Schedule's on/paused toggle state.
3. **Callout** — a bordered block of consequence, `tone × size`. Tones info / warn / bad / ok / secret; sizes inline and page-width banner (the same component with its actions on one line).
4. **AttentionBand** — the shell-level signal: amber, page-width across the content column, wording by count, a monospace countdown, and one **Take control** action. It owns the polling and the countdown tick.
5. **CountBadge** — a number riding a nav item: grey for a total, blue for in flight, amber for waiting on you.
6. **ConnectionPill** — the extension's three states, with the deliberately merged failure case.
7. **LockedCell** — a vault-sourced grid cell: purple, a lock, and the name of the Secret it draws from. Never the value.
8. **HatchedOccurrence** — a 45° 3px hatch meaning "nothing happens here": amber hatch when something prevented it (`overlap`, `missing_values`), grey when it was never due.
9. **ExpandableRow** — expand-in-place, with a rotating caret and a tinted body. Used by Schedules and Batch rows; **never** by the Runs list.
10. **StickyActionFooter** — the bottom-anchored action bar on the creation pages.
11. **EmptyState** — one bold sentence naming what is absent, one grey sentence saying what fills it, one button going there. Three parts, always.

### The four arbitrations

Each was a real disagreement between shipped prototypes. All four are settled and must not be reopened:

1. **`badge` is attributes only.** It carried two taxonomies — selector health in `prototype/workflow-editor`, step outcomes in `prototype/live-run-view`. Every lifecycle state is a StatusChip; `badge.ok` and `badge.skip` were chips wearing the wrong shape.
2. **`skipped` is grey**, not amber — in Batch rows and in Occurrences alike. Amber is reserved for "a human is needed", and no skip needs one.
3. **One callout family.** `note.*`, `banner.*`, and `driftbox` were three components for one idea. `driftbox` becomes the warn tone; `banner.gray` becomes the info tone.
4. **`--drift` is deleted.** At `#a8600b` it sat 10° of hue from `--wait` and was indistinguishable in a badge. Selector drift *is* "a human should look at this", so it is amber, told apart by its words and icon.

Also settled: `prototype/workflow-editor` is the palette outlier (`--text`/`--muted`/`--border` over a warmer `#f6f7f9`, accent `#3b5bdb`); the four-prototype set wins, and that prototype is re-skinned when `d8ux2s` is implemented — a find-and-replace with no layout change. `prototype/live-run-view`'s `--auto` is renamed `--accent`.

### Where the vocabulary lives

Three layers, so that a later session inherits the language rather than inventing one:

```
components/ui/*          shadcn, generated, never hand-edited
components/primitives/*  the eleven above, one file each
app/globals.css          the ramp and the surfaces, beside shadcn's tokens
lib/labels.ts            the single source of every state's wording
lib/copy.ts              the shared sentences
```

What shadcn supplies: StatusChip and AttributeBadge as `Badge` with two variant sets; Callout as `Alert`; the tables; ExpandableRow as `Collapsible` in a table row; EmptyState as `Card`; the shell as `Sidebar`, which already ships the icon-collapse the prototype hand-rolls; CountBadge as `SidebarMenuBadge`; and every dialog, select, input, and dropdown. What is **built here**, because the library has nothing for it: AttentionBand, LockedCell, HatchedOccurrence, ConnectionPill, StickyActionFooter, and the shared-sentence module.

**`lib/labels.ts` is the single source of every state's wording** — `waiting_for_human` reads **"needs you"** everywhere it appears, and no screen may phrase a status itself. **`lib/copy.ts`** holds the sentences that must be identical across screens, starting with the unpublished-Version sentence.

Two rules that a review can check against a diff: **no raw hex outside the token file**, and **no lifecycle state rendered except through StatusChip**.

### Cross-spec touches

All additive, and no touched spec is implemented yet:

- **`9gea5p` gains `GET /api/attention`** with the shape above, and the `runs_attention` partial index. `RunSummary` must carry the fields the Runs list renders (listed above).
- **`d8ux2s` gains the Workflow CRUD routes** and `WorkflowSummary`, including `draft_state` as the named form of the editor header's Draft chip.
- **`ufnuvx` already owns `GET /api/instance`** (unauthenticated, `signup_mode`) and the `X-Organization` header contract with its `403 code=not_a_member`; this spec consumes both — the fetch wrapper stamps the header and recognises the code.

## Dependencies

- **Next.js + TypeScript** (frontend) and **Tailwind CSS + shadcn/ui** — the stack the roadmap goal names, with the component library chosen by the user during `7mfxzj` and recorded on `ymz3md`, which still owns the versions, the layout, and the four check commands. shadcn/ui is a generator rather than a runtime dependency, but it brings the standard peers it generates against: Radix UI primitives, `lucide-react`, `class-variance-authority`, `clsx`, and `tailwind-merge`.
- **No date library.** `Intl.RelativeTimeFormat` covers "2h ago" and `Intl.DateTimeFormat` with a `timeZone` covers rendering a Schedule in its own zone with the viewer's local time trailing. Cron humanizing belongs to `nno9gj`, not here.
- **TanStack Query**, for server state. It earns its place on three counts this spec creates and later specs inherit: **deduplication** of `GET /api/auth/me`, which the shell layout and several consumers all need; **visibility-aware polling with refetch-on-focus**, which is exactly the attention endpoint's contract; and **invalidation after a mutation**, because starting or cancelling a Run makes both `/api/attention` and the Runs list stale at once, and the run detail's SSE stream must be able to invalidate the same keys. Against those, a hand-rolled fetcher is code that only grows.

  **Two defaults are mandated, not left to the library**: `mutations: { retry: false }`, because a retried `POST /api/workflows/{id}/runs` or `POST /api/schedules/{id}/run-now` is a second Run acting on a real website — the hazard `nno9gj`'s "two copies never act at once" invariant exists to prevent; and an explicit query `retry` and `staleTime` chosen per key rather than inherited. Note the distinction: `ADR 0002` forbids automatic retries of a **Run**, which is not idempotent. Refetching our own read endpoints is a different thing, and only the mutation default touches the ADR's territory.

  Like the shadcn/ui choice made during `7mfxzj`, this is a stack fact recorded on `ymz3md` rather than re-litigated later.

## Testing Decisions

Two seams.

**Seam 1 — the backend HTTP API**, tests speaking HTTP to the FastAPI app with a real Postgres. This is the same seam all five published specs use; no new machinery. Good tests here assert external behavior only: status codes, JSON shapes, and observable effects. Worked examples:

- `GET /api/attention` for an Organization with 7 `waiting_for_human` Runs → `waiting` has exactly 5 entries, soonest `deadline_at` first, and `waiting_count` is 7.
- The same call with another Organization's header → `waiting: []` and three zero counts; one Organization's waiting Runs are invisible to another.
- With 50 000 terminal Runs and 3 non-terminal ones, the query plan uses `runs_attention` and touches 3 rows — asserted by `EXPLAIN`, so the cost claim is a test rather than a hope.
- `GET /api/workflows?sort=name&limit=10` paged to exhaustion over 25 Workflows → 25 distinct ids, none seen twice, in name order, while a Run finishes mid-paging.
- `GET /api/workflows?q=acme` → only matching names, case-insensitively; `sort=activity` puts the Workflow whose Run started most recently first, and a never-run Workflow orders by its own `updated_at`.
- `POST /api/workflows/{id}/duplicate` → 201, every Step id differs from the source, order and payloads match, and the copy's `draft_state` is `never_published`.
- `DELETE /api/workflows/{id}` on a Workflow with 2 Schedules and 42 Runs → 204, and all of them plus their Artifacts are gone; the same call while a Run is `running` → `409 run_active`.
- A Workflow with no published Version in `GET /api/workflows` → `draft_state: 'never_published'` and no `published_version`; `POST /api/workflows/{id}/runs` on it → `409 no_published_version`.
- `GET /api/instance` → the configured `signup_mode`, unauthenticated, defaulting to `open` (`ufnuvx` owns the endpoint; this screen only renders it).

**Seam 2 — `resolveGate`**, a pure function, tested directly with no browser and no DOM. It is the whole guard logic, and it is the one piece of real frontend behavior this spec adds. Worked examples:

| Input | Expected |
| --- | --- |
| `(null, null, '/runs')` | redirect `/signin?next=/runs` |
| `(null, null, '/signin')` | render |
| `(ok, 'member', '/signin')` | redirect `/workflows` |
| `(ok, 'member', '/settings/organization/invitations')` | redirect `/settings/account` |
| `(ok, 'admin', '/settings/organization/invitations')` | render |
| `(ok, 'owner', '/settings/organization')` | render |
| `(null, null, '/runs?status=failed')` | redirect `/signin?next=/runs%3Fstatus%3Dfailed` |
| `next` = `https://evil.example/x` | falls back to `/workflows` |

No component or DOM tests. The eleven primitives are presentational, the lists' one behavioral rule (`workflowId` hides a column and swaps an empty state) is three lines of conditional rendering, and a rendering stack does not exist in this codebase yet — adding one to assert that is a poor trade.

## Out of Scope

- **Dark mode and any theming beyond the one light palette.** The ramp is defined once; a second palette is a later decision.
- **Widths below 880px, and any mobile layout.** The 60px icon rail at ≤1024px is the floor this spec supports. (`8iuuh8` already excluded recording on mobile.)
- **A command palette or keyboard-shortcut layer.**
- **Localization.** Copy is English; only times and numbers go through `Intl`.
- **Real-time push for the lists.** Only `/api/attention` polls and only the run detail streams; a list refreshes on navigation, on filter change, and on **Load more**.
- **Global search across Runs, Schedules, or Step content.** The Workflows list's search box is a name filter, nothing more.
- **Bulk selection and bulk actions on any list.**
- **Saved list views, filter presets, and pinned filters.**
- **Server-side rendering of list data.** Pages render the shell and fetch their own data, so one fetch wrapper can own the 401/403 redirects.
- **A live `/dev/language` route rendering the primitives.** The language's durable record is this spec.
- Everything `dm4cff` and `7mfxzj` already excluded: a dashboard or home screen; a top-level vault destination; folders, tags, and favourites on the Workflows list; a Selector Drift badge on the list row; expand-in-place rows in the Runs list; the sidebar and top-bar variants of the attention band; `--drift` as a distinct hue; `badge` as a carrier of lifecycle state; separate callout families; an amber `skipped` chip.

## Further Notes

- **This spec is the visual language's only durable record.** `prototype/app-shell` is disposable and this issue closes when it is built, so an implementer should treat the language sections above as the reference and, when they build the primitives, leave the rules where a reviewer will meet them.
- **No glossary additions.** Every domain concept here — Workflow, Run, Schedule, Batch, Secret, Auth State, Organization, Membership, Invitation, Occurrence — is already defined. The primitives are UI vocabulary, not domain vocabulary.
- **No ADR.** The far-reaching decision in the area is the attention band, and it is cheap to reverse; the stack facts belong to `ymz3md`.
- **`ymz3md` is a prerequisite in practice**: it establishes the stack and the four check commands, and this is the first spec whose implementation is mostly frontend. The session that lands it should expect to set up Tailwind, shadcn, and the frontend test runner that Seam 2 needs.
- **Build order that keeps each step verifiable**: the sign-in screen and `resolveGate` first (they gate everything and need no lists), then the shell with the Organization switcher and the attention band, then the Workflows list with its CRUD routes, then the two shared lists, then Settings and the first-run panel.
- Provenance for anything ambiguous above: node `dm4cff` (the map) and node `7mfxzj` (the look and the language), whose notes carry the reasoning, and branch `prototype/app-shell`, whose LANGUAGE tab renders every primitive with the earlier prototype it came from.

## Notes

**claude** — 2026-08-15T04:13:45Z

Edited 2026-08-15 for ADR 0005 (Organization tenancy, passwordless Sign-in Codes): /signup and /set-password are gone (one two-step /signin), the gate takes an org role instead of is_admin/must_change flags, the fetch wrapper stamps X-Organization and handles not_a_member, Settings' Admin group became the Organization group (General/Members/Invitations), the sidebar user menu gains the Organization switcher, and the attention endpoint/index scope by org_id. GET /api/instance now lives in ufnuvx as signup_mode.
