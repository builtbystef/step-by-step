---
id: idnzwf
title: 'Step by Step: record, edit, and replay browser workflows — roadmap'
state: in-progress
assignee: builtbystef
priority: high
labels:
    - roadmap
created: 2026-08-08T07:07:08Z
updated: 2026-08-15T04:14:42Z
---

## Goal

A user can install a Chrome extension, record actions they perform on a website (navigate, click, type, select, download, extract data) as a named workflow of editable semantic steps; edit that workflow in a web app; run it on demand, on a schedule, or as a batch over a list of input rows; watch runs live with the ability to take over when the site demands a human (CAPTCHA, MFA) and hand control back; and review each run's artifacts (screenshots, traces, downloads, extracted data).

Under the hood: Next.js/TypeScript frontend, FastAPI/Python backend, versioned workflows in PostgreSQL, Redis-queued executions on isolated Playwright workers, separate artifact storage, and securely handled auth state and secrets.

Related but outside this DAG: issue `ymz3md` (establish stack, checks, and dev commands) — the first implementation session lands it.

## Frontier

<!-- In-scope questions that are too vague to be nodes. They become nodes as the roadmap advances. -->

Every decision node under this roadmap is closed, and all six areas are specced: `ufnuvx` (accounts), `d8ux2s` (recording, editing, storage), `54i6da` (Secrets and Auth State), `9gea5p` (execution, Workers, the live run view), `nno9gj` (creating Batches and Schedules), and `pc0t8s` (the app shell, the lists, and the visual language — the frame the other five each assumed and none described, from `dm4cff`'s map and `7mfxzj`'s look). **Only the Frontier remains**, so the next `advance-plan` session's job is the Frontier itself: interview until its sharpest entry becomes nodes. Note that `pc0t8s` is the visual language's only durable record — no `docs/` file holds it — and that `ymz3md` still owns the stack, now carrying three recorded facts (shadcn/ui over Tailwind, TanStack Query with `mutations: {retry: false}`, and no date library).

- Extracted data delivery *outside the app*: webhook, API, or push on completion. (The per-step schema settled in ds8zyn; the in-app half settled in apx4rs and spec 9gea5p — a Run's Output tab and `GET /api/runs/{id}/output?format=json|csv`, and the same across a Batch's rows.)
- Saved reusable datasets (a list-of-rows entity that outlives one batch) — revisit when usage shows the reuse pattern; v1 batches own their rows (8iuuh8), and reuse is a copy: tf6796 settled "copy rows from a past Batch" as a toolbar action that fills the new Batch's grid.
- Monorepo layout, local dev environment, deployment target and hosting. (The service list settled in px25yw: one docker compose stack — backend, Workers, Postgres, Redis, Garage — the Artifact store being Garage rather than MinIO since 2026-08-16, MinIO having archived its community edition; see px25yw. Spec 9gea5p adds what a Worker image must carry: Xvfb, x11vnc, a minimal window manager. The *frontend* half narrowed twice: 7mfxzj chose shadcn/ui over Tailwind, and `pc0t8s` added TanStack Query with two mandated defaults. Both are recorded on `ymz3md`, which still owns the framework version, the monorepo layout, and the four check commands — plus, now, a frontend test runner able to exercise a pure module with no DOM.)
- Observability for the operator: worker health, pool saturation, instance metrics. (The primitives exist — worker heartbeats on Run rows, log-line events over Redis pub/sub — and spec 9gea5p builds no dashboard on them. How a Run's log lines read to its owner settled in apx4rs and 9gea5p: a Logs tab in the run detail's drawer, and per-step lines inside an expanded step.)
- Chrome Web Store publication of the extension — deferred by n52g83, not rejected. It needs a developer account, review turnaround, permission justification for `debugger` and broad optional host access, and a decision between an unlisted and a public listing. Revisit when unpacked installation becomes the thing that hurts.

## Out of scope

<!-- Items excluded on purpose. The list only grows. One line for each item, with the node's ref when it was one. An item never moves back in. -->

- ~~Teams, sharing, and org roles — accounts are personal; multi-tenant means isolated users (8iuuh8).~~ Reversed by ADR 0005 (2026-08-15): the tenant is the Organization, with owner/admin/member roles and Invitations. Billing and entitlements stay out of scope.
- Hosted/paid SaaS offering — self-hosted open source now; hosted is a possible future (8iuuh8).
- Loop, conditional, and assertion step types inside a workflow (8iuuh8).
- Reusing a step's extracted output as a later step's input; computed/derived variables (8iuuh8).
- One-off "run at a specific time" scheduling and interval-since-last-run mode (8iuuh8).
- Parallel execution of runs within a batch — sequential only (8iuuh8).
- Notifications (email/push) for runs waiting on takeover or failed (8iuuh8).
- Secrets supplied via CSV / batch rows (8iuuh8).
- Browsers other than Chrome (Firefox/Safari extensions) (8iuuh8).
- Recording on mobile (8iuuh8).
- rrweb (or any session-replay library) as the source of recorded steps (f10wq3) — it emits no portable element identity, only session-local integer ids resolved inside its own rebuilt DOM. It remains a candidate for *viewing* a run, never for producing one.
- Self-healing selectors for v1: DOM-tree-comparison healing (Healenium-style) and automatic selector regeneration after a failure (f10wq3) — no first-party or peer-reviewed evidence validates any shipped self-healing product, and a ranked list of record-time-verified alternatives captures most of the benefit. Revisit only with run data showing what actually breaks.
- Weighted multi-locator voting at replay for v1 (f10wq3) — the 29.5% robustness gain was measured across five XPath generators on 2015-era apps, and voting can let converging broken locators out-vote correct ones. Ordered fallback over a ranked list is the v1 policy; `wljln8` confirms it.
- Pinning a Schedule or Batch to a specific Version (ds8zyn) — they always execute the latest published Version; pinning is addable later as an optional version pointer.
- Nested/hierarchical extraction records (ds8zyn) — an extract step yields a named scalar or a flat list of records with named fields.
- Dynamic per-run container spawning and worker autoscaling (px25yw) — a fixed pool of Worker containers; the backend never holds Docker-socket privileges. Concurrency scales by redeploying with more replicas.
- Automatic Run-level retries (px25yw; ADR 0002) — Runs act on external websites and replay is not idempotent. Retrying exists only inside a step.
- A reserved Worker pool for takeover-capable Runs (px25yw) — a waiting_for_human Run occupies a regular Worker slot until resume or timeout.
- Pure master-detail (IDE-style) and pure narrative-sentence editor layouts (3iwv5i) — the editor is the hybrid: an inline card list whose card summaries are the narrative sentences.
- Full-screen focus-page and modal takeover surfaces (4tjwpw) — the takeover surface is the browser pane embedded in the run detail; entering takeover never navigates away. Auto hand-back on a met success predicate (with a short grace countdown and a "stay in control" escape) is the confirmed behavior; heuristic pauses, having no predicate, stay manual.
- Cloud KMS integration for Secret/Auth State encryption (7o0nmx; ADR 0003) — v1 is an env-supplied 32-byte master key with app-level envelope encryption; losing the key means stored values are unrecoverable by design.
- Per-workflow secret values (7o0nmx) — Secrets live in the Organization's vault (ADR 0005; Personal Overrides per member) and workflows bind by name; one rotation point.
- Per-domain locks or freshness stamps for Auth State write-back (7o0nmx) — concurrent same-user same-domain runs are last-write-wins; worst case is one extra login/takeover on the next run.
- Suppressing screenshots on secret-referencing steps (7o0nmx) — password fields mask themselves and that is accepted; trace capture is bracketed around those steps instead, and log lines are redacted.
- Silent Auth State export from the extension (7o0nmx) — capture is an explicit per-domain opt-in prompt at recording save.
- A closable/reopenable debugger infobar during recording (zm0rfq) — dismissing the bar detaches `chrome.debugger`, ending role/name capture, and Chrome offers no reopen. The recording UX presents the bar as the fixed, visible cost of an active recording.

- OAuth/OIDC/SSO sign-in for v1 (imtsfx, revised by ADR 0005) — sign-in is an emailed Sign-in Code; OIDC is a clean later addition.
- Passwords in any form (ADR 0005) — no password sign-in, storage, reset, or recovery CLI exists; every sign-in proves the email address.
- Soft delete / deletion grace period (imtsfx) — account and Organization deletion are hard cascades behind type-to-confirm.
- Billing, plans, entitlements, seat limits; audit logging of membership actions; custom roles or multiple owners (spec ufnuvx).
- CDP response-body capture (spec u8q8p3) — no v1 step type consumes network bodies: extract reads the DOM, download uses chrome.downloads. Nothing network-level is retained, so no filtering policy is needed.
- Replaying a Workflow to position the page for a Re-pick (spec u8q8p3) — the user navigates to the page themselves; re-pick stays free of Worker machinery.
- Revealing a stored Auth State blob in the UI, any audit log of reveals or vault changes, and any re-authentication gate before Secret reveal (spec 54i6da, revised under ADR 0005) — a session blob has nothing a human can read usefully; Secret reveal is deliberately ungated, since the account password a sudo gate would re-enter no longer exists and any member can exfiltrate a value through a Run regardless.
- Expiry, TTL, refresh-ahead, or health-checking of stored Auth State (spec 54i6da) — a site's real session lifetime is invisible to us, so a stale record simply fails to authenticate and a login Step or takeover recovers.
- Automatic capture of a domain a Run signs into, outside takeover consent (spec 54i6da) — new records come only from the recording-save opt-in or an explicit "keep this login?" at hand-back.
- Per-Worker credentials and TLS on the Worker↔backend internal endpoints (spec 54i6da) — a shared compose token plus a non-terminal-Run check; a fixed compose pool has no provisioning step to hang per-Worker credentials on, and Workers are never internet-facing.

- Timeline-spine and three-column ops-console layouts for the run detail (apx4rs) — the run detail is the cockpit: a step rail, the embedded browser pane as the main pane, and a Logs/Output/Artifacts drawer. The spine's two advantages, per-step inline expansion and control phases shown inside the step sequence, were grafted into the cockpit instead.
- Time-travel scrubbing of a Run — a draggable gantt that reconstructs the page state at an arbitrary instant (apx4rs) — it requires per-moment reconstruction for a payoff that per-step screenshots already give, and it crowded the layout at laptop width.
- Master-detail batch progress (a row list beside one row's detail) (apx4rs) — the batch progress view is a table whose rows expand in place, because a batch's work is scanning many rows for the few that need attention.

- `externally_connectable`-based app-to-extension messaging (n52g83) — its match patterns forbid wildcard domains and subdomains of effective TLDs, so no single build can name an arbitrary self-hosted origin. The extension opens the channel instead.
- Self-hosted `.crx` with an `update_url`, and extension auto-update of any kind, for v1 (n52g83) — off-store `.crx` installs work on Linux only, and the instance serves the build that pairs with it.
- Enterprise-policy deployment of the extension (n52g83) — a documented escape hatch for Windows/macOS fleets, not a supported v1 path.

- Artifact retention, age- or size-based garbage collection, and storage quotas (spec 9gea5p) — Artifacts live until their Run or account is deleted; a terminal Run can be deleted, which purges its objects.
- Event replay on reconnect — a Redis event buffer or `Last-Event-ID` on the SSE stream (spec 9gea5p) — a reconnecting client refetches the Run over REST, because Postgres already holds every durable fact and a second source of truth could only disagree with it.
- A task/queue framework — arq, Celery, RQ (spec 9gea5p) — dispatch is a Redis list plus a conditional claim on the Run row, and a framework would bring its own retry policy, which ADR 0002 forbids.
- Catch-up of missed scheduled occurrences (spec 9gea5p) — an instance down all night does not fire six 09:00 Runs when it returns; the occurrences are skipped and `next_due_at` moves forward.
- Automatic pausing of a Run on heuristic challenge detection (spec 9gea5p) — the diagnostic informs the user and classifies a subsequent failure as `auth_challenge`; taking control stays the user's decision.
- Per-Worker or per-Run VNC credentials, and concurrent takeover by two sessions (spec 9gea5p) — shared compose-supplied view-only and control credentials, enforced at the backend proxy, with one holder session at a time.

- A staged wizard for Batch creation, and a column-mapping screen on every import (tf6796) — creation is one grid-first page whose columns are the Workflow's Variables, so typing, pasting, importing, and reusing a past Batch's rows are the same surface. A mapping strip appears only when reconciliation is not confident.
- Discarding incomplete rows at Batch creation, and refusing to create a Batch that has any (tf6796) — a row missing a value becomes a `skipped` row, so it stays visible and re-runnable through machinery spec 9gea5p already has. An empty Variable can be legitimate, so "run them anyway" remains available.
- Silently dropping an uploaded column whose name matches a secret Variable (tf6796) — the drop is named on screen and happens client-side, so those values never reach the backend.

- Preset tiles as the whole recurrence surface, and a raw cron field as the primary control (pjxuqx) — entry is a sentence of dropdowns with preset chips that fill it, and the generated cron shown beneath, always. Tiles alone drop the user onto bare cron at the first intermediate case; cron-first demands knowledge the product's premise says they do not have.
- Guessing a plain-language reading for any cron expression (pjxuqx) — an expression the humanizer cannot phrase shortly says so, and the real next occurrences stand as the answer.
- Default values declared on a Workflow's Variables as the source of an unattended Run's inputs (pjxuqx) — the value set is owned by the Schedule, so two Schedules of one Workflow can differ and no default leaks into manual Runs or Batch rows.
- Silent prefill of a Schedule's values from the last manual Run (pjxuqx) — an explicit "fill from my last Run" button instead; silent prefill enshrines a throwaway or test Run's values in a job that then fires unattended forever.
- Creating a Schedule with a Variable left empty (pjxuqx) — unlike a Batch row, which becomes a `skipped` row and stays visible (tf6796), an incomplete Schedule fails unattended on repeat, so it cannot be saved.
- A per-Workflow Schedules surface separate from the global one (pjxuqx) — one all-Schedules table with rows expanding in place; the Workflow's Schedules tab is that same component, filtered.

- A built-in column-alias dictionary for CSV import (spec `nno9gj`) — a near match is a suggestion shown inside the mapping strip and never applied silently, so there is no alias table to maintain.
- Server-side CSV upload, storage, or parsing (spec `nno9gj`) — the file is parsed in the browser, which is what makes the loud client-side drop of a secret-named column true.
- A global Batches index across Workflows (spec `nno9gj`) — the instance-wide question belongs to the all-Schedules table; Batches are listed per Workflow, behind the "copy rows from a past Batch" picker.
- Recording fired Occurrences as their own rows (spec `nno9gj`) — the Run carrying the `schedule_id` is that record, and only non-firing Occurrences are persisted.
- Overriding the skip-on-overlap rule from the UI (spec `nno9gj`) — "run it now instead" is refused while a Run of that Schedule is still non-terminal; two copies never act on one site at once.
- Editing a Batch's name after creation, and reordering or inserting rows into an existing Batch (spec `nno9gj`).

- A dashboard or home screen (dm4cff) — sign-in lands on Workflows, and it would be a third rendering of rows the Runs and Schedules lists already own. `8iuuh8`'s "visible on the dashboard" is kept by the shell instead: an attention band on every screen while any Run is `waiting_for_human`, and a badge on the Runs nav item.
- A top-level vault destination (dm4cff) — Secrets and Saved logins are sections of Settings, as `54i6da` itself describes them.
- Folders, tags, and favourites on the Workflows list (dm4cff) — a search box and a sort control; forty rows is a scroll, not a taxonomy.
- A Selector Drift badge on the Workflows list row (dm4cff) — it needs an aggregate no endpoint provides, and `d8ux2s` deliberately put drift where repair happens (the editor), with `9gea5p` showing it where it was observed (the run detail).
- Expand-in-place rows in the Runs list (dm4cff) — a Run row navigates to the cockpit, which is a full screen with a live browser pane; expand-in-place stays for batch rows and Schedules.

- The attention band inside the sidebar, and as a pill in a persistent top bar (7mfxzj) — Shell A puts it across the content column, above the page title. The sidebar version can name only one waiting Run and costs sidebar height; the top-bar pill is the quietest of the three, which is wrong for the one signal whose reason to exist is a 30-minute deadline that fails the Run when it passes.
- `--drift` as a colour token distinct from `--wait` (7mfxzj) — at #a8600b it sat 10° of hue from #b97a08 and was indistinguishable in a badge. Selector drift *is* "a human should look at this", so it is amber, told apart by its words and icon.
- `.badge` as a carrier of lifecycle state (7mfxzj) — badges are attributes only; every lifecycle state is a `.chip`. The two prototypes that gave `.badge` two different taxonomies are reconciled that way.
- Separate `.banner` and `.driftbox` callout families (7mfxzj) — one callout component, tone × size. A page-width banner is the same component with actions on one line.
- An amber `skipped` chip (7mfxzj) — skipped is neutral grey, whether it is a Batch row missing a value or an Occurrence skipped for overlap. Amber is reserved for "a human is needed".

- Dark mode, and any theming beyond the one light palette (`pc0t8s`) — the semantic ramp is defined once; a second palette is a later decision.
- Mobile layouts and any width below 880px (`pc0t8s`) — the 60px icon rail at ≤1024px is the floor. `8iuuh8` already excluded recording on mobile.
- A command palette or keyboard-shortcut layer (`pc0t8s`).
- Localization (`pc0t8s`) — copy is English; only times and numbers go through `Intl`.
- Real-time push for the lists (`pc0t8s`) — only `/api/attention` polls and only the run detail streams; a list refreshes on navigation, on filter change, and on Load more.
- Global search across Runs, Schedules, or Step content (`pc0t8s`) — the Workflows list's search box is a name filter, nothing more.
- Bulk selection and bulk actions on any list, and saved list views or filter presets (`pc0t8s`).
- Server-side rendering of list data (`pc0t8s`) — pages render the shell and fetch their own data, so one fetch wrapper owns the 401/403 redirects.
- A live `/dev/language` route rendering the primitives (`pc0t8s`) — the language's durable record is the spec, not a screen.

## Notes

**claude** — 2026-08-14T05:34:47Z

STACK LANDED (2026-08-14): ymz3md is done, so the body's "ymz3md still owns the stack / framework version / monorepo layout / check commands" is now stale — all of it is settled and built. The grill session's full decision record and the scaffold outcome are notes on ymz3md; the durable records are docs/ARCHITECTURE.md (layout, seams, strictness, test tiers) and AGENTS.md (the check commands: pnpm check / pnpm test). Highlights: monorepo scaffolded from the user's alloy template — apps/web (Next 16), apps/api (FastAPI, Python 3.14, SQLAlchemy 2 + Alembic scaffold, no tables yet), packages/api-client (generated, CI contract job) — with apps/worker and apps/extension decided but landing with their first slices. The frontend facts recorded on ymz3md (shadcn/ui over Tailwind, TanStack Query with mutations retry:false, no date library) remain binding on the slices that install them; none are installed yet.

With all six areas specced and the stack landed, the next sessions break the specs into buildable sub-issues (TRACKER.md: build a spec's sub-issues, never the spec).

**claude** — 2026-08-15T04:14:42Z

Direction change 2026-08-15, recorded as ADR 0005 (supersedes ADR 0001): the product is shaped as a SaaS without billing — Organization tenancy (auto-org at signup, owner/admin/member roles, Invitations), passwordless Sign-in Code auth via a mailer seam (Resend/SMTP/console), no Instance Admin, SIGNUP_MODE env var. The accounts spec ufnuvx is rewritten; qf0lu8 and 8wxso0 are cancelled; t7jki2/3nxs4k/x06w5q/jrp1pq/o99b7t/lac27w/shurgk/hat4cf are repurposed; ycn8xm (mailer seam) is new; the vault spec 54i6da is labeled needs-review for org re-scoping with Personal Overrides.
