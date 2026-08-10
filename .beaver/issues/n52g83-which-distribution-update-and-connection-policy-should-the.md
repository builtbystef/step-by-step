---
id: n52g83
title: Which distribution, update, and connection policy should the v1 Chrome extension use?
state: todo
labels:
    - roadmap:idnzwf
    - session:grill
depends_on:
    - 1zg7o0
parent: idnzwf
created: 2026-08-10T02:26:59Z
updated: 2026-08-10T02:26:59Z
---

Choose v1 extension distribution and update policy now that 1zg7o0 settled the recorder/auth boundary.

Decide:
- Chrome Web Store publication, unpacked developer installation, or another supported distribution path for v1;
- whether self-hosted deployments use one shared extension build and the implications for stable extension ID;
- update channel and compatibility/minimum Chrome version (the recorder may require Chrome 118+ for debugger-session worker liveness);
- confirm the direct extension-to-backend handshake: the app initiates an allowlisted connection, backend mints a short-lived recording-scoped credential, extension calls backend directly.

Read the 1zg7o0 research note before the decision.
