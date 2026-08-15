---
id: 5yu03g
title: 'The VNC path: tickets and server-side view-only'
state: todo
priority: medium
depends_on:
    - qmnvgr
parent: 9gea5p
created: 2026-08-14T07:43:37Z
updated: 2026-08-14T07:43:37Z
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
