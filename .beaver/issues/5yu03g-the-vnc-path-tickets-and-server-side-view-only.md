---
id: 5yu03g
title: 'The VNC path: tickets and server-side view-only'
state: done
assignee: agent
priority: medium
depends_on:
    - qmnvgr
parent: 9gea5p
created: 2026-08-14T07:43:37Z
updated: 2026-08-25T19:40:35Z
---

## What to build

The pipe from the Worker's browser to the user's screen, with control enforced where the user cannot tamper with it. The backend is the only thing that connects to a Worker's VNC server. `GET /api/runs/{id}/vnc?ticket=…` (WebSocket) validates the ticket, the Run's ownership and non-terminal state, then pipes RFB frames between client and Worker. A view-only ticket comes from `POST /api/runs/{id}/stream-ticket` (any non-terminal Run, for watching); the takeover endpoint's ticket grants control.

View-only is enforced server-side: the proxy authenticates to the Worker's VNC server with the view-only credential unless the connecting session currently holds takeover, in which case it uses the control credential. A takeover ending — hand-back, abandon, timeout — drops and reopens the connection view-only; the noVNC client is never trusted to restrain itself. Both credentials come from the compose environment, shared across Workers. Workers stay unreachable from the internet; the endpoint each Worker reported at claim is where the proxy connects.

## Acceptance criteria

- [ ] A stream ticket for an owned running Run opens a WebSocket that delivers RFB frames from that Run's Worker; input events sent through it change nothing on the page (view-only credential).
- [ ] A takeover holder's connection accepts input: keystrokes through the socket land in the Worker's browser.
- [ ] The takeover ending closes the control connection; reconnecting with a fresh stream ticket is view-only again.
- [ ] A ticket is single-use and expires: redeeming twice fails, redeeming after the TTL fails.
- [ ] Another user's Run id → 404 with no ticket minted and no connection attempted; a terminal Run → no connection.
- [ ] A second session of the owner can hold a view-only connection while the first holds control.

## Notes

**claude** — 2026-08-17T04:03:47Z

Re-scope per ADR 0005: 'the Run's ownership' is org Membership via X-Organization — another Organization's Run id → 404; any member of the Run's Organization may mint stream tickets and take over (54i6da: a takeover by a different member does not re-resolve credentials).

**agent** — 2026-08-25T19:19:17Z

Seams from the parent spec: backend HTTP/WebSocket against Postgres (and a local fake RFB server standing in for the Worker). Covers stream-ticket minting, single-use/TTL redeem, org-scoped 404 with no Worker connection, terminal refusal, view-only vs control VNC credentials, takeover-end closing the control socket, and a second session watching while the first holds control. The pane UI is 2aybf8.

**agent** — 2026-08-25T19:40:35Z

Completed the VNC path: stream tickets and server-side view-only.

POST /api/runs/{id}/stream-ticket mints a 60s single-use ticket for any non-terminal Run in the active Organization (409 run_terminal otherwise; another Organization's id is 404 and no row is written). GET /api/runs/{id}/vnc?ticket=… spends the ticket, checks the session is a member of the Run's Organization, and pipes RFB to the Worker endpoint on the row. The proxy authenticates to x11vnc with VNC_VIEW_PASSWORD unless that session currently holds takeover and has not handed back, in which case it uses VNC_CONTROL_PASSWORD. Hand-back, holder release, or a terminal Run closes a control socket; a fresh stream ticket is view-only. Two sessions can share the Worker (x11vnc -shared).

Workers write both passwords into an x11vnc passwdfile at boot. Compose and .env.example carry the shared dev defaults. OpenAPI and the generated client include mintStreamTicket.
