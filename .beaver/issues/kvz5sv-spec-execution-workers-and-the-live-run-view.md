---
id: kvz5sv
title: 'Spec: execution, workers, and the live run view'
state: done
assignee: claude
labels:
    - roadmap:idnzwf
    - session:spec
depends_on:
    - px25yw
    - 1ar6xu
    - 4tjwpw
    - apx4rs
parent: idnzwf
created: 2026-08-11T19:45:28Z
updated: 2026-08-17T01:01:44Z
---

Write the spec for the execution area (session:spec). The area's nodes: execution architecture — isolation, queue semantics, streaming (px25yw, with ADR 0002); mid-run browser takeover research (1ar6xu); takeover UX prototype (4tjwpw); live run view and timeline prototype (apx4rs).

Read those nodes' notes and linked artifacts (this area's only). Interview to close remaining gaps (grill-me), confirm with the user, then invoke the create-specification skill. Publish the spec issue with a blocking edge back to each node it covers.

Boundaries already fixed by neighbouring specs:

- The recording/editing/storage spec (d8ux2s) owns the Step document, the Draft/Version model, and the selector resolution module contract (`resolve(page, target, deadline)`, ordered fallback, ambiguity rejected, timeout as the retry budget). This spec consumes them; it does not redefine them.
- The secrets spec (000gz2) owns the Secret vault and Auth State storage. This spec consumes their injection and write-back contract.
- Accounts and authentication are spec ufnuvx.

This spec owns: Run lifecycle and statuses, the Redis queue and Worker pool, per-Run browser isolation, Step Result writing, Artifact production and storage, the SSE event stream, the scheduler loop, Batch execution, cancellation, takeover (enter, control, hand back, timeout), and the live run and batch views.

## Notes

**claude** — 2026-08-12T01:02:24Z

Spec published: **9gea5p — Execution, Workers, and the live run view**, with blocking edges back to px25yw, 1ar6xu, 4tjwpw, and apx4rs. The user approved the draft in full.

The spec owns: Run lifecycle and the closed failure_reason set; Redis dispatch and the conditional Worker claim; the Run executor; cancellation, pause, and Takeover (enter, control, verify, hand back, timeout, abandon); the VNC path and server-side view-only enforcement; the challenge diagnostic; the SSE event set; Artifacts; the scheduler loop; Batch execution; and the cockpit run detail plus the batch table.

Gaps this session closed by interview (none of them settled by any node):

- **Live view transport** — the pane is one VNC connection for the whole Run, view-only until Takeover flips it interactive. Not periodic screenshots swapped for VNC at takeover: one transport, one code path.
- **Worker command channel** — the Run row is the authority, the Redis control channel is the nudge. Pub/sub alone can drop a command; polling alone makes cancel feel slow.
- **Reconnection** — no event buffer, no Last-Event-ID. A reconnecting client refetches the Run over REST and subscribes from now on; Postgres already holds every durable fact.
- **Artifacts** — screenshots are per-Step and **off by default** (the user's revision: 200 steps would mean 200 screenshots), always captured on a failing Step, never during waiting_for_human; one chunked trace per Run yielding several Artifacts; retention **none** in v1, with DELETE of a terminal Run purging its MinIO objects; access by short-lived presigned URL after an ownership check.
- **Scheduler semantics** — cron plus IANA timezone; overlap → skip the occurrence; missed occurrences → never caught up. A host down all night does not fire six 09:00 Runs on return.
- **Batch mechanics** — rows advance on the terminal-status event the backend already consumes, with the periodic loop as backstop; skip-a-row cancels its Run and advances; re-run-a-row is a new attempt on the same row; ETA is the median of completed rows, hidden until three finish.
- **Takeover authorization** — single-use short-TTL ticket, backend-proxied WebSocket, view-only enforced at the proxy via the VNC server's own credentials, one holder session at a time.
- **Challenge heuristic** — raised only when a Step has burned half its timeout AND the page carries a known provider signal; it informs, never pauses by itself, and turns a subsequent step_failed into auth_challenge.
- **Log persistence** — a run_log_lines table written by the Worker and streamed in parallel, capped at 10k lines with a truncation marker.
- **Run again** — prefills the normal run dialog with the Run's Variable values against the latest published Version; repeating a Run stays deliberate (ADR 0002).

Seams the user agreed to: (1) the backend HTTP API, with the scheduler tick and batch-advance invoked directly as functions and asserted through that surface; (2) the Worker's Run executor, driving a real browser over fixture pages and asserting on what it writes. No UI seam — apx4rs and 4tjwpw validated the views by prototype.

Two additive amendments to published spec d8ux2s, noted on that issue: Step envelope gains `screenshot?: boolean`; `pause-for-takeover` gains `successCheck?: Target` (4tjwpw's success predicate had nowhere to live).

Glossary: **Takeover** added.

**claude** — 2026-08-17T01:01:44Z

CORRECTION (2026-08-16): where the Artifacts bullet says "purging its MinIO objects", read Garage. MinIO archived its community edition read-only on 2026-04-25 (abandoned, not relicensed), and the Artifact store is now Garage. Nothing else in this node changes — screenshots off by default, always on a failing Step, never during waiting_for_human; one chunked trace per Run; retention none in v1; access by short-lived presigned URL after an ownership check. Garage supports presigned URLs. Full reasoning on px25yw; stack fact on ymz3md; the live text is in spec 9gea5p.
