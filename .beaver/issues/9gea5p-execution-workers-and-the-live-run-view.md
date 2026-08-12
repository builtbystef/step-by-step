---
id: 9gea5p
title: Execution, Workers, and the live run view
state: todo
labels:
    - spec
depends_on:
    - px25yw
    - 1ar6xu
    - 4tjwpw
    - apx4rs
created: 2026-08-12T01:01:52Z
updated: 2026-08-12T01:01:52Z
---

# Execution, Workers, and the live run view

## Problem Statement

A published Workflow is inert. Everything the user recorded and edited only pays off when it runs — on demand, at 3 a.m. on a Schedule, or fifty times over a list of rows — and running is where every hard thing lives. The actions are real: a click submits a real form on someone else's website, so a Run that is retried, resumed at the wrong place, or aborted mid-click can do damage no undo reaches. The sites fight back: a login demands an MFA code, a page throws a CAPTCHA, and the automation has no way through — but the user, watching, does. And afterwards the user has to know what happened without reading logs like a developer: which Step failed and why, what the page looked like at that moment, whether the workflow is quietly drifting toward breaking, and where the data it extracted went.

## Solution

A fixed pool of Workers, each executing at most one Run at a time in its own headed Chromium with a throwaway profile. Postgres holds the truth; Redis is the dispatch pipe carrying nothing but Run ids. A Worker loads the Version, injects the user's Auth State and Secrets, walks the Steps, and writes what it sees — Step Results, log lines, screenshots, trace chunks, downloads — as it goes.

The user watches this in one screen: a cockpit whose main pane is the Worker's actual browser, streamed over VNC through the backend. While automation runs the pane is view-only. When a Run reaches a `pause-for-takeover` Step — or the user pauses it over a suspected CAPTCHA — the Run parks in `waiting_for_human`, keeps its browser alive, and the same pane becomes interactive. The user solves the challenge, and control returns either explicitly or automatically when the Step's success check passes. A timeline strip above the Steps shows who had control, when, and for how long.

Runs reach the pool three ways: a user starts one, a Schedule's cron fires, or a Batch feeds its rows through one at a time. Nothing is ever retried automatically (ADR 0002); a Run that dies says why in a machine-readable `failure_reason` and waits for a human decision.

## User Stories

1. As a user, I want to run a Workflow on demand and supply its Variable values, so that I can use what I recorded.
2. As a user, I want a Run to wait its turn when every Worker is busy, so that a burst of work finishes rather than failing.
3. As a user, I want to watch my Run's actual browser as it works, so that I can see what it is doing rather than infer it from logs.
4. As a user, I want a Run that hits a login or CAPTCHA to stop and wait for me instead of failing, so that a human-only step does not cost me the whole Run.
5. As a user, I want to take control of that browser, solve the challenge, and hand it back, so that automation continues from where it stopped.
6. As a user, I want control to return by itself once the workflow's success check passes, so that forgetting to hand back does not waste a Worker.
7. As a user, I want a run that waits too long for me to end cleanly with a reason, so that a Worker is not held forever by a Run I abandoned.
8. As a user, I want to cancel a Run and know it stops at a Step boundary rather than mid-click, so that cancelling cannot leave a half-submitted form.
9. As a user, I want each Step's result, screenshots I asked for, and its own log lines, so that I can tell what a failure actually was.
10. As a user, I want to see when a Step was found by a lower-ranked selector, so that I can repair a target before it breaks entirely.
11. As a user, I want the data a Run extracted as a table I can download as CSV or JSON, so that the automation produces something I can use.
12. As a user, I want a Schedule to run my Workflow on a cron expression in my own timezone, so that recurring work happens without me.
13. As a user, I want a scheduled occurrence skipped when the previous Run is still going, so that two copies never act on the same site at once.
14. As a user, I want to run a Workflow over a list of rows and watch the rows progress, so that fifty repetitions are one action.
15. As a user, I want a failed row to leave the rest of the Batch running, and to re-run just that row afterwards, so that one bad input does not cost the whole job.
16. As a user, I want to know when a Batch is stalled because one row needs me, so that a queue that stopped moving is never a mystery.
17. As an operator, I want a Run whose Worker died to be marked failed rather than hanging forever, so that the pool recovers by itself.

## Implementation Decisions

### Entities (shape, not migration)

- **`runs`** — id, user_id, workflow_id, version_id (null for a test run), draft_snapshot JSONB (test runs only), is_test, trigger (`manual` | `schedule` | `batch` | `test`), schedule_id, batch_row_id, status, failure_reason, failure_detail, variables JSONB (**non-secret values only**; secret Variables carry the binding, never the value), timeout_ms, worker_id, worker_vnc_endpoint, heartbeat_at, cancel_requested_at, pause_requested_at, takeover_holder_session_id, takeover_deadline_at, auto_handback_disabled, queued_at, started_at, ended_at, automation_ms.
- **`step_results`** — one row per Step the Run reached: run_id, step_id (the Version document's stable uuid), position, status (`passed` | `failed` | `skipped`), started_at, ended_at, matched_candidate_rank, candidate_count, completed_by_human, error_code, error_message, diagnostics JSONB, extracted_value JSONB.
- **`run_control_intervals`** — run_id, kind (`automation` | `waiting` | `human` | `verifying`), started_at, ended_at. This table *is* the timeline strip, and `automation_ms` / time-with-you are sums over it rather than separately maintained counters.
- **`run_log_lines`** — run_id, seq, step_id (nullable), level, at, text. Capped at 10 000 lines per Run; the cap emits one final `log truncated` line and further lines are dropped, never buffered.
- **`artifacts`** — run_id, step_id (nullable), kind (`screenshot` | `trace` | `download`), object_key, content_type, size_bytes, index, created_at.
- **`schedules`** — workflow_id, user_id, cron, timezone (IANA), enabled, last_fired_at, next_due_at, last_skip_reason, created_at.
- **`batches`** — id, user_id, workflow_id, name, created_at, cancelled_at. **`batch_rows`** — batch_id, index, variables JSONB, status (`queued` | `running` | `succeeded` | `failed` | `skipped` | `cancelled`). A row's Runs point back at it; the row's status and output reflect its **latest attempt**. Batch counts are always derived from rows, never stored twice.

### Run lifecycle

```
queued ──▶ running ⇄ waiting_for_human
             │              │
             └──────┬───────┘
                    ▼
     succeeded | failed | cancelled          (terminal)
```

`failure_reason` (v1, closed set):

| reason | meaning |
| --- | --- |
| `step_failed` | a non-optional Step failed — selector failure, action error, or timeout |
| `auth_challenge` | a Step failed while the challenge diagnostic was present (the classification u7nkwh asked for) |
| `takeover_timeout` | the `waiting_for_human` deadline passed |
| `takeover_abandoned` | the user chose "give up — fail the run" during takeover |
| `run_timeout` | accumulated automation time exceeded the Workflow's run timeout |
| `worker_lost` | the heartbeat went stale |
| `missing_secret` | a bound Secret no longer exists (54i6da's `missing_secret`, raised at Run start) |
| `startup_failed` | the browser or Auth State injection failed before Step 1 |

`waiting_for_human` covers the waiting, human-control, and verifying phases: the status chip shows the Run state, the control-interval strip shows who held control. A Step Result is written for **every** Step of the Version — the ones after a failure or a cancellation are `skipped`, so a Run's Step Result count always equals its Step count.

### Dispatch

- Enqueue is `LPUSH` of a Run id onto one Redis list. A Worker `BRPOP`s, then **claims the Run with a conditional update** (`status = 'queued'` → `running`, stamping worker_id, worker_vnc_endpoint, started_at, heartbeat_at). A claim that updates zero rows means the Run was cancelled or already taken; the Worker drops it and pops again. Redis is never asked to be reliable.
- The backstop for a lost Redis job: the backend loop re-enqueues any Run still `queued` past a threshold with no worker assigned. A duplicate id in the list is harmless — the conditional claim rejects it.
- A Worker heartbeats its Run's row every few seconds. The backend loop marks any non-terminal Run whose heartbeat is stale `failed` / `worker_lost` and writes `skipped` Step Results for whatever the Run never reached.
- **Queue library: none.** `redis-py` primitives (`LPUSH`/`BRPOP`) plus the conditional claim are the whole mechanism; a task framework would add a second scheduler and a second retry policy, and ADR 0002 forbids the retries it would bring.

### The Worker's Run executor

Per Run, in order:

1. Claim the Run; open a fresh headed Chromium on the Worker's X display with a throwaway profile directory.
2. Fetch credentials from the backend (`GET /internal/runs/{id}/credentials`, 54i6da). A `missing_secret` response fails the Run before anything is touched. Secret values live in Worker memory for the Run's duration and are registered with the redaction filter immediately.
3. Create the browser context with **all** of the user's Auth State loaded (54i6da's inject-all rule), start trace capture, seed `sessionStorage` per origin via init script.
4. For each Step, in order: skip if `disabled`; resolve its Target through the module d8ux2s defines (`resolve(page, target, deadline)`, ordered fallback, ambiguity rejected, the timeout is the retry budget); perform the action; write the Step Result with the matched candidate's rank (the Selector Drift signal); capture a screenshot if the Step's toggle is on; publish `step.started` / `step.finished`.
5. At every **Step boundary** — and between candidate-walk iterations inside a resolve loop, where nothing has been clicked yet — check the control state: cancellation requested, pause requested, or a takeover already granted. This is the only place automation yields; an action in flight always completes.
6. On terminal: assemble nothing (output is derived from Step Results on read), stop the trace, write back Auth State if the Run succeeded (54i6da), close the browser, delete the profile directory, set the terminal status.

**Failure of a non-optional Step stops the Run** (wljln8): executed Steps keep their results, the rest are written `skipped`, and the Run is `failed` / `step_failed` — or `auth_challenge` when the challenge diagnostic was present on that Step. An `optional` Step whose target never appears is `skipped` and the Run continues.

**Run timeout counts automation only.** The Worker accumulates automation time across `automation` intervals; time in `waiting`, `human`, and `verifying` never counts. Exceeding the Workflow's run timeout (default 30 min) at a Step boundary → `failed` / `run_timeout`.

### Control: cancellation, pause, takeover

**Cancellation** is allowed in any non-terminal state:

- `queued` → the row flips to `cancelled` at once; the Worker's conditional claim later fails and drops the job.
- `running` → `cancel_requested_at` is stamped and a control message published; the Worker stops at the next boundary, marks the remaining Steps `skipped`, and ends `cancelled`. The UI states this rule in words and shows a "cancelling — waiting for step N to reach a boundary" band meanwhile.
- `waiting_for_human` → nothing is in flight, so the takeover ends and the browser closes immediately.

**Commands reach the Worker two ways, and the row is the authority.** The backend writes the request to the Run row and publishes it on the Run's Redis control channel; the Worker acts on the message when it arrives and re-reads the row at every boundary regardless. A dropped pub/sub message costs latency, never correctness.

**Entering `waiting_for_human`** happens on either of:

- a `pause-for-takeover` Step — the Run parks *before* the Step's work, with the Step's author-written message shown to the user;
- a user pause request (the CAPTCHA banner's "pause run & take over") — honored between resolve-loop iterations of the stuck Step, so the Step's action has not started.

On entry the Worker opens a `waiting` control interval and the takeover deadline is stamped: the Workflow's takeover timeout (default 30 min) or the Step's override. **One clock covers waiting plus human control plus verifying** — the countdown does not restart when the user takes control.

**Taking control.** `POST /api/runs/{id}/takeover` mints a single-use, short-TTL ticket and records the holding session; the client opens the VNC WebSocket with it. Control is held by **one session at a time**: a second tab of the same user gets a view-only pane and a note saying where control is. The Worker suspends automation entirely while a `human` interval is open — it only polls the success check (a read-only resolve, never an action, safe alongside human input).

**The success check.** The `pause-for-takeover` payload gains an optional `successCheck: Target` — the element whose appearance means the human is done (see *Cross-spec touches*). Where it is present:

- its live met/unmet state streams to the UI while waiting and during control;
- when it becomes met during control, a **6-second grace countdown** starts and control hands back automatically. "Hand back now" skips the grace; "stay in control" sets `auto_handback_disabled` for the remainder of that takeover. The grace exists so a site that chains a second prompt does not yank control away mid-task.

Where it is absent — always the case for a heuristic pause — hand-back is manual only.

**Handing back** (`POST /api/runs/{id}/handback`) opens a `verifying` interval:

- **success check present and met** → automation resumes at the next Step (the pause Step's own Step Result is `passed` with `completed_by_human`);
- **present and unmet** → the Run does *not* resume: it returns to `waiting`, the browser stays held, and the user chooses "keep control and finish it" (a fresh `human` interval) or "give up" (`POST /api/runs/{id}/takeover/abandon` → `failed` / `takeover_abandoned`);
- **absent** → automation resumes by **retrying the Step it paused on** with a fresh Step timeout budget.

**Timeout.** The deadline passing in any of the three phases ends the Run `failed` / `takeover_timeout`; the browser closes and the pane reports "session ended".

**Auth State consent at hand-back.** At hand-back the Worker reports registrable domains that gained a session and have no stored record; the run detail offers "keep this login for site.com?", and a consented domain joins the next write-back (54i6da owns the endpoints and the write-back rules).

### The browser pane and the VNC path

- Each Worker runs one X display (Xvfb), one window manager, and one VNC server bound to the compose network only — never published to the host. A Worker reports its VNC endpoint on the Run row when it claims a Run.
- The backend is the **only** thing that connects to it. `GET /api/runs/{id}/vnc?ticket=…` (WebSocket) validates the ticket, the Run's ownership and state, then pipes frames to the Worker. Workers are never internet-facing.
- **View-only is enforced server-side.** The proxy authenticates to the Worker's VNC server with the view-only credential unless the connecting session currently holds takeover, in which case it uses the control credential. A takeover ending drops and reopens the connection view-only. The noVNC client is never trusted to restrain itself. Both credentials come from the compose environment, shared across Workers — the same posture as 54i6da's shared internal token, and for the same reason: a fixed compose pool has no per-Worker provisioning step.
- The pane connects only while a client has the Run open, and connects for any non-terminal Run — a view-only ticket (`POST /api/runs/{id}/stream-ticket`) is minted for watching, a takeover ticket for controlling.

### The challenge diagnostic

The Worker raises a `suspected_challenge` diagnostic when **both** hold: a Step has been resolving for at least 50% of its timeout, **and** the page carries a known challenge signal — an iframe whose host matches a small built-in provider list (reCAPTCHA, hCaptcha, Cloudflare Turnstile/challenges) or a well-known challenge container. The list is a constant in the Worker; it is not user-configurable and not extensible at runtime.

The diagnostic streams as an event (the dismissible banner offering "pause run and take over") and is attached to the Step Result if that Step ultimately fails, which is what turns `step_failed` into `auth_challenge`. It never pauses a Run by itself — no heuristic takes control away from the user's own judgment.

### Events and streaming

Workers publish to `run:{id}:events` on Redis pub/sub; the backend subscribes and fans out over SSE. The backend also acts on the terminal-status event itself, to advance a Batch without waiting for its periodic loop. Commands travel over REST, never over the stream. Screenshot and trace **bytes never enter the stream** — an event announces an Artifact, the client fetches it by URL.

```
GET /api/runs/{runId}/events        (SSE)
GET /api/batches/{batchId}/events   (SSE)

run.status    { run_id, status, failure_reason?, failure_detail?, at }
step.started  { run_id, step_id, position, at }
step.finished { run_id, step_id, status, matched_candidate_rank, candidate_count,
                completed_by_human, extracted_count?, at }
control       { run_id, phase: "automation"|"waiting"|"human"|"verifying",
                deadline_at?, at }
predicate     { run_id, met: bool, grace_ends_at?, at }
diagnostic    { run_id, step_id, kind: "suspected_challenge", detail, at }
log           { run_id, seq, step_id?, level, text, at }
artifact      { run_id, step_id?, artifact_id, kind, at }
batch.row     { batch_id, row_index, status, run_id?, at }
```

**Reconnection replays nothing.** A client that reconnects refetches the Run over REST — status, Step Results, control intervals, log lines, artifacts are all in Postgres — and subscribes from now on. There is no event buffer and no `Last-Event-ID`; a second source of truth for data Postgres already holds would only be a way to disagree with it.

**Redaction happens in the Worker before publishing** (54i6da): every secret value bound to the Run is replaced with `••••` in log lines, error strings, and failure detail, with no minimum length.

### Artifacts

- **Screenshots** are per Step and **off by default**. A Step's `screenshot` toggle turns capture on for that Step. A **failing** Step is always screenshotted regardless of its toggle — that is diagnostics, not a preference. No screenshot is taken while a Run is in `waiting_for_human` (54i6da: nothing may catch an MFA code mid-type).
- **Trace**: Playwright tracing runs for the whole Run, chunked — a chunk is stopped before every secret-referencing Step and restarted after it, and paused across takeover. A Run therefore yields several trace Artifacts with an `index`, each openable in Trace Viewer; that is a consequence of the bracketing, not an accident.
- **Downloads** are captured as they are produced and stored with their suggested filename.
- Workers write objects to MinIO directly and insert the `artifacts` row themselves (px25yw). Bytes never pass through the backend.
- **Access**: `GET /api/runs/{id}/artifacts/{artifactId}/download` checks Run ownership, then redirects to a short-lived presigned URL.
- **Retention: none in v1.** Artifacts live until their Run is deleted. `DELETE /api/runs/{id}` (terminal Runs only) purges the Run, its Step Results, log lines, and its MinIO objects; ufnuvx's account cascade does the same in bulk. There is no age-based or size-based garbage collection.

### The scheduler loop

One loop in the backend, running each minute, doing four things and nothing else:

1. **Fire due Schedules** — for each enabled Schedule whose next occurrence has passed, create a Run of the Workflow's **latest published Version** and enqueue it. Cron expressions are evaluated in the Schedule's IANA timezone (defaulting to the instance's).
2. **Overlap → skip.** If a Run from that same Schedule is still non-terminal, the occurrence is skipped, `last_skip_reason` records it, and the UI can say so. Two copies of one Workflow never act on a site at once.
3. **Missed occurrences → skipped entirely**, never caught up. An instance down all night does not fire six 09:00 Runs when it returns; `next_due_at` moves to the next future occurrence.
4. **Reap and backstop** — stale-heartbeat Runs to `worker_lost`, over-deadline `waiting_for_human` Runs to `takeover_timeout`, long-`queued` Runs re-enqueued, and stalled Batches advanced.

A disabled user's Schedules do not fire (ufnuvx). Cron-expression *editing UI* is not this spec's (see Out of Scope); the engine's behavior is.

### Batches

A Batch's rows execute **sequentially**: exactly one Run of a Batch is non-terminal at a time.

- **Advance** is driven by the terminal-status event the backend already consumes for SSE fan-out — the next `queued` row's Run is created and enqueued there, with the periodic loop as a backstop for a missed event. There is no minute-long gap between rows.
- **A failed row never strands the Batch** (wljln8): the Batch advances and the failed row shows its reason in place.
- **Skip a row** (`POST /api/batches/{id}/rows/{n}/skip`) — offered while a row waits on a human: that row's Run is cancelled, the row becomes `skipped`, the Batch advances at once.
- **Re-run a row** (`POST /api/batches/{id}/rows/{n}/rerun`) — a new attempt attached to the same row, becoming the row's current Run; previous attempts stay listed. It disturbs no other row and does not reopen a finished Batch.
- **Cancel a Batch** — the current Run is cancelled and every remaining row becomes `cancelled` (px25yw).
- **ETA** = median duration of completed rows × rows remaining, shown only once at least three rows have finished; blank before that rather than wrong.
- A row waiting on a human stalls the Batch by design, and the view says so in words (below).

### HTTP API contract

User-facing, session cookie (ufnuvx), every route scoped to the calling user:

```
POST   /api/workflows/{id}/runs      {variables, test?: bool}   → 201 {run_id}
                                       409 code=missing_secret {variable_names}
GET    /api/runs?workflow_id=&status=&limit=&cursor=            → 200 [RunSummary]
GET    /api/runs/{id}                → 200 {run, step_results, control_intervals,
                                             artifacts, batch_row?}
GET    /api/runs/{id}/logs?after_seq=&step_id=                  → 200 [LogLine]
GET    /api/runs/{id}/output?format=json|csv                    → 200 assembled output
GET    /api/runs/{id}/artifacts/{artifactId}/download           → 307 presigned URL
DELETE /api/runs/{id}                → 204 (terminal Runs only; purges MinIO objects)
                                       409 code=run_active

POST   /api/runs/{id}/cancel         → 202
POST   /api/runs/{id}/pause          → 202  (request takeover at the next safe boundary)
POST   /api/runs/{id}/stream-ticket  → 200 {ticket, ws_url, expires_at}   (view-only)
POST   /api/runs/{id}/takeover       → 200 {ticket, ws_url, expires_at, deadline_at}
                                       409 code=not_waiting | code=already_held
POST   /api/runs/{id}/takeover/hold  {auto_handback: bool}       → 204
POST   /api/runs/{id}/handback       → 202
POST   /api/runs/{id}/takeover/abandon                           → 202
GET    /api/runs/{id}/vnc?ticket=…   → WebSocket (RFB frames)

POST   /api/workflows/{id}/batches   {name, rows: [{variables}]} → 201 {batch_id}
GET    /api/batches/{id}             → 200 {batch, rows, stats, eta_seconds?}
GET    /api/batches/{id}/output?format=json|csv                  → 200 uniform table
POST   /api/batches/{id}/cancel                                  → 202
POST   /api/batches/{id}/rows/{n}/skip                           → 202
POST   /api/batches/{id}/rows/{n}/rerun                          → 201 {run_id}

GET    /api/workflows/{id}/schedules → 200 [{id, cron, timezone, enabled,
                                             last_fired_at, next_due_at, last_skip_reason}]
POST   /api/workflows/{id}/schedules {cron, timezone, enabled}   → 201
                                       400 code=invalid_cron | code=invalid_timezone
PATCH  /api/schedules/{id}           {cron?, timezone?, enabled?} → 200
DELETE /api/schedules/{id}                                        → 204
```

Internal, Worker → backend, the shared compose token plus the non-terminal-Run check (54i6da's posture; the credentials and auth-state routes are 54i6da's own):

```
POST /internal/runs/{runId}/heartbeat   {worker_id, vnc_endpoint} → 204
                                          409 code=run_terminal    (the Worker aborts)
GET  /internal/runs/{runId}/control     → 200 {cancel_requested, pause_requested,
                                               takeover_phase, auto_handback_disabled}
```

Everything else a Worker writes — Step Results, log lines, control intervals, artifacts rows, run status — goes directly to Postgres through the shared internal library (px25yw), and events go directly to Redis.

### The run detail and the batch view (web app)

Settled by prototypes 4tjwpw and apx4rs; restated here as requirements, not re-decided.

**Run detail — the cockpit.** A left rail of Steps; the embedded browser pane as the main pane; a Logs / Output / Artifacts drawer beneath it; a compact timeline strip under the header.

- **Header**: workflow name, run id, Version, trigger, status chip, and a meta row of elapsed · automation time · time with you · steps done · worker · timeout, plus `failure_reason` once terminal. A `⚠ N steps drifted` chip appears when any Step resolved on a low-ranked candidate.
- **Timeline strip**: proportional control intervals — automation (blue), waiting for you (amber striped), you in control (purple), verifying (teal) — with event markers beneath (paused · you took control · handed back · resumed) and a legend. It renders `run_control_intervals` directly.
- **Step rail**: number, editable label, the narrative sentence matching the editor (3iwv5i), duration, and badges — drift (`found on candidate 3/5`), "completed by you · verified ✓", selector failure, skipped, record and file counts. A Step expands in place into its error, its drift panel (the ranked candidates: which died, which matched, and a link to Re-pick in the editor), its screenshots, its extracted data, and its own log lines. Control phases appear inline in the rail between Steps as compact bands ("waiting for you — 0:06", "you were in control — 0:11", "verifying the success check — 0:02 · passed, automation resumed").
- **Pane**: view-only while automation runs ("view only — automation in control"), amber-highlighted while waiting, interactive during takeover, with the purple control bar above it (identity of the controlled browser, the countdown turning red when low, "hand control back", "cancel run") and the success-check line beneath it.
- **Waiting card**: the reason, the countdown, the success check's live state, "take over browser", "cancel run".
- **Terminal**: the pane holds the final page ("session ended — the browser closed") and a banner states the outcome in words (`succeeded in 0:39 · 8 of 8 steps · 24 records · 1 download`, or `failed at step 6 · step_failed · remaining 2 steps skipped` with a "re-pick the element" action). The Output tab renders the assembled object as a table with Download JSON / CSV; Artifacts lists screenshots, trace chunks (Open in Trace Viewer), and downloads.
- **Run again**: opens the normal run dialog prefilled with this Run's Variable values, executing the latest published Version. Repeating a Run is always a deliberate act (ADR 0002).
- **Cancel**: an inline confirm stating the rule in plain language, then the "cancelling…" band.

**Batch view — the table.** Rows as a table (number, the row's Variable values, status chip, duration, live badge on the running row), a stats header (done / succeeded / failed / queued / skipped), and a segmented progress bar with the ETA. Any row expands in place: the live row into a mini run view (control strip, Step list, log tail, "open the full run"), a failed row into its reason plus "open the run" and "re-run just this row", a succeeded row into its output. When the current row enters `waiting_for_human`, an amber callout above the table names the row, states that rows run one at a time and the others stay queued, shows the countdown and what a timeout does (this row fails, the Batch moves on), and offers "take over row N" / "skip this row". The Batch's Output tab is the uniform table across rows with download-all.

### Cross-spec touches

Both are additive, and neither spec is implemented yet:

- **d8ux2s's Step envelope gains `screenshot?: boolean`** (default `false`) — per-Step screenshot capture, rendered in the editor's right-hand badge column beside optional / off / timeout.
- **d8ux2s's `pause-for-takeover` payload gains `successCheck?: Target`** — the element whose appearance means the human is done. It reuses the `Target` shape and the `resolve` contract; absent means manual hand-back only. Without it, 4tjwpw's verified hand-back and auto hand-back have nothing to check.

## Dependencies

- **redis-py** — the dispatch list, the control channel, and the event pub/sub. No task framework (arq, Celery, RQ): the mechanism is two list operations and a conditional claim, and a framework would bring its own retry policy, which ADR 0002 forbids.
- **croniter** — cron expression parsing and next-occurrence computation. Timezone handling is the standard library's `zoneinfo`; no other scheduling library.
- **boto3** (or the `minio` client) — S3-compatible object writes from Workers and presigned URL minting in the backend.
- **@novnc/novnc** — the browser-side RFB client for the pane. Writing an RFB client is not a side quest.
- **Worker image system packages: Xvfb, x11vnc, and a minimal window manager.** The display, the VNC server, and sane handling of the browser's own dialogs and popups. These are image packages, not Python dependencies.

Playwright, FastAPI, Postgres, and Next.js are already the project's.

## Testing Decisions

**Seam 1 — the backend HTTP API.** The same seam d8ux2s, 54i6da, and ufnuvx use: tests speak HTTP to the FastAPI app with a real Postgres and Redis. The **scheduler tick and the batch-advance step are invoked directly as functions** and asserted through this surface, which keeps time-driven behavior testable without a clock harness and without a third seam (the technique 54i6da used for the Worker's publish helper).

Worked examples:

- Start a Run while every Worker is busy → 201 and status `queued`; the Run id is on the Redis list exactly once.
- Cancel a `queued` Run → status `cancelled` at once, and a subsequent claim attempt for that id updates zero rows.
- Cancel a `running` Run → 202 and `cancel_requested_at` set, status still `running` — the API never fakes a stop the Worker has not made.
- A Run whose `heartbeat_at` is older than the threshold, then one scheduler tick → `failed` / `worker_lost`, and every unreached Step has a `skipped` Step Result.
- A `waiting_for_human` Run past its deadline, then one tick → `failed` / `takeover_timeout`.
- Two ticks a minute apart for a Schedule with `0 9 * * *` in `Europe/Belgrade` → exactly one Run created, and `next_due_at` is tomorrow 09:00 local, not UTC.
- A Schedule whose previous Run is still `running`, then a tick at the next occurrence → no Run created, `last_skip_reason` = overlap.
- A tick after a six-hour gap covering three missed occurrences → one Run at most is **not** created; zero catch-up Runs exist and `next_due_at` is in the future.
- `POST /api/runs/{id}/takeover` on a `running` Run → 409 `not_waiting`; on a `waiting_for_human` Run → a ticket; a second call from another session → 409 `already_held`; the ticket redeemed twice → the second is refused.
- A Batch of five rows: driving each row's Run to terminal advances exactly one row at a time, and at no point are two of the Batch's Runs non-terminal.
- A Batch whose row 2 fails → rows 3–5 still run; `rerun` on row 2 → a new Run attached to row 2, the row's status follows the new attempt, and the earlier attempt is still listed.
- Cancel a Batch mid-row-3 → row 3's Run cancelled, rows 4–5 `cancelled`.
- `GET /api/runs/{id}/output?format=csv` for a Run with a list-mode extract of 24 records → 24 data rows with the field names as the header; the Batch's output over five rows → one table whose columns are the union of Variables and output names.
- `DELETE` a `running` Run → 409 `run_active`; a terminal one → 204 and its MinIO objects are gone.
- An artifact download request from a second user's session → 404, and no presigned URL is minted.
- The log cap: 10 001 published lines → 10 000 rows plus the truncation line, and the endpoint's last line says truncated.

**Seam 2 — the Worker's Run executor.** Hand it a Version and local fixture pages, let it drive a real Playwright browser, and assert on what it writes out: Step Result rows, run status transitions, control intervals, objects in MinIO, and events published to Redis. Everything below it — selector resolution, actionability, trace bracketing — is observable here; the resolution module has its own tests in d8ux2s.

Worked examples:

- A three-Step Version over fixture pages → three `passed` Step Results in order, `succeeded`, and one `automation` control interval covering the Run.
- A Step whose top candidate is gone but whose rank-2 candidate matches → `passed` with `matched_candidate_rank` = 2 (the drift signal the header chip counts).
- A non-optional Step whose target never appears → that Step `failed`, every later Step `skipped`, run `failed` / `step_failed`; an `optional` Step in the same position → `skipped` and the Run continues.
- Screenshot toggles: a Version with the toggle on for Step 2 only → exactly one screenshot Artifact from a successful Run; the same Version where Step 3 fails → two, the second belonging to the failed Step.
- A cancellation requested while Step 2 is mid-action → Step 2's Step Result is complete (never truncated), Steps 3+ are `skipped`, run `cancelled`.
- A `pause-for-takeover` Step → run `waiting_for_human`, a `waiting` interval opened, the browser still alive, and no screenshot Artifact produced during the wait.
- Hand-back with a met `successCheck` → a `verifying` interval, then `automation` resumes at the next Step, and the pause Step's result carries `completed_by_human`.
- Hand-back with an unmet `successCheck` → the Run returns to `waiting`, does not advance, and abandoning yields `failed` / `takeover_abandoned`.
- A heuristic pause (no `successCheck`) → hand-back retries the same Step with a fresh timeout budget rather than advancing.
- A fixture page embedding a challenge iframe on a Step that stalls past half its timeout → a `suspected_challenge` diagnostic event; when that Step then fails → `failure_reason` = `auth_challenge`, not `step_failed`.
- A Version whose Step 2 types a Secret → the trace has a hole at Step 2 (chunk boundaries around it), and a log line containing the secret value arrives on Redis as `••••` with no fragment of the value.
- A Run that fails → no Auth State write-back is attempted at all; a Run that succeeds → write-back for existing records only (54i6da's endpoint enforces the rest).

Prior art: none yet in the repository. The accounts spec (ufnuvx) lands the HTTP harness and Postgres fixtures both seams reuse; d8ux2s lands the Playwright fixture-page harness that seam 2 extends.

## Out of Scope

- Automatic Run-level retries of any kind (ADR 0002).
- Dynamic per-Run container spawning and Worker autoscaling; a reserved Worker pool for takeover-capable Runs (px25yw).
- Parallel execution of a Batch's rows — sequential only (8iuuh8).
- Pinning a Schedule or Batch to a specific Version (ds8zyn) — they execute the latest published Version.
- Artifact retention, age- or size-based garbage collection, and storage quotas — Artifacts live until their Run or account is deleted.
- The Batch **creation** UI: uploading rows, mapping columns to Variables, naming and re-running a whole Batch (Frontier). This spec lands the endpoint that a Batch needs to exist and execute.
- The Schedule **editing** UI: cron-expression builders, human-readable previews, timezone pickers (Frontier). The engine's semantics are settled here.
- Delivery of extracted data outside the app — webhooks, push, an outbound API (Frontier). Download and in-app tables are here.
- Notifications (email/push) when a Run needs a human or fails (8iuuh8).
- Operator-facing observability: worker health dashboards, pool saturation, instance metrics (Frontier). Heartbeats and log lines are the primitives; no dashboard is built.
- CDP screencast as a pane transport (1ar6xu) — a later page-only optimization, not v1.
- Time-travel scrubbing of a Run, and master-detail batch progress (apx4rs).
- Full-screen and modal takeover surfaces (4tjwpw) — the pane is embedded.
- Automatic pausing on a heuristic challenge detection — the diagnostic informs, the user decides.
- Secret and Auth State storage, encryption, injection endpoints, and write-back rules (54i6da) — consumed here, owned there.
- The Step document, the Draft/Version model, and the selector-resolution module (d8ux2s) — consumed here, owned there.
- Accounts, sessions, and admin powers (ufnuvx) — this spec only honors disable and delete.

## Further Notes

- **Two published specs gain a field** (see *Cross-spec touches*): d8ux2s's Step envelope gains `screenshot`, and its `pause-for-takeover` payload gains `successCheck`. Neither spec is implemented yet, so both are edits, not migrations.
- Reference prototypes, disposable — steal patterns, not code: branch `prototype/takeover-ux` (`PROTOTYPE-takeover-ux.html`, the full takeover lifecycle including auto hand-back) and branch `prototype/live-run-view` (`PROTOTYPE-live-run-view.html`, the cockpit, the control-interval strip, the batch table, a working cancel).
- ADR 0002 (no automatic Run retries) governs this spec throughout; ADR 0004 (Workers never hold the master key) governs its credential path.
- The `waiting_for_human` Run holding its Worker slot is an accepted v1 cost (px25yw). An instance whose Workers are all parked on humans has no queued work moving, and nothing in v1 mitigates that beyond the takeover timeout.
- u7nkwh established that a transferred session can fail for reasons invisible to us (device-bound cookies, token binding, fingerprinting). v1 predicts nothing: a failed authentication is classified `auth_challenge` and routed to a login Step or a takeover. Do not add heuristics that guess.
- Glossary: **Takeover** is added by this spec. Every other term it uses — Run, Step Result, Worker, Batch, Schedule, Artifact, Version, Selector Drift — is already defined.
