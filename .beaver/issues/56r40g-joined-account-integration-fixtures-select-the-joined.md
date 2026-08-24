---
id: 56r40g
title: Joined-account integration fixtures select the joined Organization
state: todo
priority: high
labels:
    - bug
created: 2026-08-24T10:13:30Z
updated: 2026-08-24T10:13:30Z
---

## Problem

The service-backed API tier has four tenant-isolation failures because `tests/integration/conftest.py::join` returns an `Account` whose `org_id` names the owner's Organization while its shared TestClient still sends the invitee's original `X-Organization`. Auth State and Secret tests therefore correctly receive empty lists or 404s from the wrong active Organization. The Auth State store test also uses `github.io`, which is a public suffix rather than a registrable domain and is correctly refused by the production validator.

## Acceptance criteria

- [ ] The Account returned by `join` sends the returned `org_id` as `X-Organization`; callers that need another active Organization switch it explicitly.
- [ ] The personal-only Auth State fixture uses a registrable domain while still exercising a domain distinct from the Organization layer.
- [ ] The affected Auth State and Secret integration tests pass without weakening tenant isolation or registrable-domain validation.
- [ ] The full API integration tier is green apart from failures owned by another explicit issue.

## Evidence

`pnpm test:integration` on 2026-08-24: Auth State listing returned no rows for a joined member; Secret reveal/override/list returned 404 or no rows; constructing an Auth State for `github.io` raised "has no registrable domain".
