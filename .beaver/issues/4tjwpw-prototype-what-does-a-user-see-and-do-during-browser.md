---
id: 4tjwpw
title: 'Prototype: what does a user see and do during browser takeover?'
state: todo
priority: high
labels:
    - roadmap:idnzwf
    - session:prototype
depends_on:
    - 1ar6xu
parent: idnzwf
created: 2026-08-10T02:27:52Z
updated: 2026-08-10T02:27:52Z
---

Live prototype session (prototype skill). The takeover research `1ar6xu` settles the technical boundary: a per-run isolated headed Chromium session, user access to that same session through an authenticated web VNC gateway, automation suspended during human control, and an explicit `humanAuth` / `humanChallenge` step with a workflow-defined success predicate.

Answer with disposable UI:

- How does a waiting run appear, and how does a user enter/exit takeover safely?
- What browser view, run status, timer, and security context are visible while the user completes CAPTCHA/MFA?
- How does the user explicitly hand control back; how is the configured success predicate shown, verified, or failed?
- What happens on timeout, user cancellation, or an unexpected challenge detected heuristically?
- How does the run timeline distinguish automation, human control, and resume events?

Inputs: research note `1ar6xu`, docs/GLOSSARY.md, and the execution-architecture node `px25yw` once it resolves. This prototype feeds its area spec.
