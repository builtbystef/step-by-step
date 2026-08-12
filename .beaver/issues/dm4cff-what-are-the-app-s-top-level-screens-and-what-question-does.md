---
id: dm4cff
title: What are the app's top-level screens, and what question does each one answer?
state: todo
priority: high
labels:
    - roadmap:idnzwf
    - session:grill
parent: idnzwf
created: 2026-08-12T03:51:49Z
updated: 2026-08-12T03:51:49Z
---

One live interview (grill-me), limited to information architecture. Five specs describe deep surfaces — the editor (d8ux2s), the vault (54i6da), the run detail and batch progress (9gea5p), Batch and Schedule creation (nno9gj) — and every one of them assumes a frame around it that no spec describes. Settle that frame:

- **The Workflows list.** The screen a user lands on after signing in. What does a row show, what actions hang off it, how is a new Workflow started, and how does it sort or filter once there are forty?
- **Runs history.** `9gea5p` ships `GET /api/runs?workflow_id=&status=&cursor=` and specifies the run *detail*, but nothing renders the list that detail is reached from. Is it a global screen, a tab on a Workflow, or both — and what question is it there to answer? Note that `nno9gj` already ruled the instance-wide "is anything unattended broken?" question to be the all-Schedules table's job.
- **The shell.** What are the top-level destinations (Workflows, Runs, Schedules, Batches, vault, settings, admin), and what is the navigation between them? Where do the Instance Admin's screens live so that they are reachable without being underfoot for a single-user instance?
- **Auth screens.** `ufnuvx` settles the rules and the endpoints — sign-in, sign-up (open or closed), forced password change on first login, admin user management. Where do those screens sit, and which of them are outside the shell?
- **Empty and first-run states.** No Workflows yet, extension not installed, a Workflow with no published Version, a Workflow with no Runs. These are the first thing a new user of a self-hosted instance sees, and `n52g83` settled that installation is unpacked and manual, which makes the first-run path longer than a hosted product's.
- **The word "dashboard."** `8iuuh8` said a Run waiting on a human is "visible on the dashboard" and no spec has built one. Decide whether such a screen exists at all, or whether the lists already answer it.

Inputs: the five published specs (`ufnuvx`, `d8ux2s`, `54i6da`, `9gea5p`, `nno9gj`), `docs/GLOSSARY.md`. Do not re-decide anything those specs settled; this node draws the map they hang on.

The answer gates the shell-and-lists prototype, and with it the visual language.
