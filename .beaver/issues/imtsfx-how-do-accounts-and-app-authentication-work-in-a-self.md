---
id: imtsfx
title: How do accounts and app authentication work in a self-hosted multi-tenant deployment?
state: todo
priority: medium
labels:
    - roadmap:idnzwf
    - session:grill
depends_on:
    - 8iuuh8
parent: idnzwf
created: 2026-08-08T07:53:28Z
updated: 2026-08-08T07:53:28Z
---

One live interview (grill-me). Tenancy is settled (node 8iuuh8: multi-tenant with personal accounts, no teams/sharing, self-hosted open source, org-hostable). Decide:

- Sign-in method: email/password, OAuth providers, or both — for a self-hosted instance an org runs for its people.
- User provisioning: open signup vs. admin-created accounts vs. invite; is there an instance admin, and what can they do (v1 minimum)?
- Session/token model for the web app, and what the backend issues.
- Password reset and account recovery in a self-hosted deployment (no email service guaranteed).

Related but separate: extension-to-backend authentication stays on the Frontier under extension distribution.
