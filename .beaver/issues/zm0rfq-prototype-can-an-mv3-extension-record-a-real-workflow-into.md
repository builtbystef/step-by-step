---
id: zm0rfq
title: 'Prototype: can an MV3 extension record a real workflow into semantic steps?'
state: todo
priority: medium
labels:
    - roadmap:idnzwf
    - session:prototype
depends_on:
    - f10wq3
    - 1zg7o0
parent: idnzwf
created: 2026-08-08T07:08:04Z
updated: 2026-08-08T07:08:04Z
---

Disposable prototype (prototype skill), live with the user. With selector strategy (f10wq3) and MV3 capabilities (1zg7o0) researched, answer by building:

- Record a small real flow (e.g. log in to a demo site, search, extract a value, download a file) with a throwaway extension using the chosen capture approach.
- Do the captured events map cleanly to the intended semantic steps with durable selectors?
- Replay the captured steps once in Playwright to expose the record→replay gap early.

Feasibility verdict + findings gate the data-model decisions hardening into a spec; the code is disposable.
