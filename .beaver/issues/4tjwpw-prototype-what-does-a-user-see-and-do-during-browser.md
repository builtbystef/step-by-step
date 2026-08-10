---
id: 4tjwpw
title: 'Prototype: what does a user see and do during browser takeover?'
state: done
assignee: claude
priority: high
labels:
    - roadmap:idnzwf
    - session:prototype
depends_on:
    - 1ar6xu
parent: idnzwf
created: 2026-08-10T02:27:52Z
updated: 2026-08-10T06:46:49Z
---

Live prototype session (prototype skill). The takeover research `1ar6xu` settles the technical boundary: a per-run isolated headed Chromium session, user access to that same session through an authenticated web VNC gateway, automation suspended during human control, and an explicit `humanAuth` / `humanChallenge` step with a workflow-defined success predicate.

Answer with disposable UI:

- How does a waiting run appear, and how does a user enter/exit takeover safely?
- What browser view, run status, timer, and security context are visible while the user completes CAPTCHA/MFA?
- How does the user explicitly hand control back; how is the configured success predicate shown, verified, or failed?
- What happens on timeout, user cancellation, or an unexpected challenge detected heuristically?
- How does the run timeline distinguish automation, human control, and resume events?

Inputs: research note `1ar6xu`, docs/GLOSSARY.md, and the execution-architecture node `px25yw` once it resolves. This prototype feeds its area spec.

## Notes

**claude** — 2026-08-10T06:46:49Z

## Question

What does a user see and do during browser takeover? Answered with a disposable UI prototype (branch `prototype/takeover-ux`, file `PROTOTYPE-takeover-ux.html` — one self-contained HTML page simulating the full lifecycle with a fake VNC browser and three switchable layouts). Verdict is the user's: "everything feels right … the new UX is good, the rest sounds good also", plus one requested change (auto hand-back) that was added and approved.

## Verdict

**Layout: C — embedded pane.** The browser view is a permanent pane inside the run detail (rejected: A full-screen focus page, B modal — see roadmap Out of scope). The same pane serves three modes: read-only live view while automation runs ("view only — automation in control" badge), amber-highlighted preview of the held browser while waiting, and the interactive VNC surface during takeover. One surface for watching and intervening; entering takeover never navigates away from the run.

**Waiting run.** When a Run hits `waiting_for_human`, the run detail shows an amber "This run is waiting for you" card: the reason (the pause-for-takeover step's name, or "you paused it over a suspected CAPTCHA"), a countdown to the takeover timeout, the success predicate with live met/not-met status, and two actions — "Take over browser" and "Cancel run".

**During takeover.** A purple control bar sits above the browser pane with: "You are controlling this browser", security context (run id · worker · site · encrypted, only you can see this session), the takeover countdown (turns red/pulsing when low), "Hand control back", and "Cancel run". Below the pane, a predicate line shows the configured success check with live met/unmet status.

**Hand-back and verification.** Hand-back is explicit at any time. It enters a distinct *verifying* interval (teal): the worker checks the success predicate. Pass → automation resumes at the next step. Fail → the run does NOT resume; the browser stays held and the user chooses "Keep control & finish it" or "Give up — fail the run".

**Auto hand-back (added at user request — they kept forgetting to hand back).** When the success predicate becomes met while the user is in control, a ~6-second grace countdown starts in the predicate line ("✓ met — handing back in 6s"), then control hands back automatically. Escape hatches: "Hand back now" (skip the grace) and "Stay in control" (cancels auto for that takeover; it stays manual until the user hands back). The grace period exists so control isn't yanked away if the site chains a second prompt after login. Auto hand-back applies only where a success predicate exists.

**Unexpected challenge (heuristic).** During automation, a stuck step plus a CAPTCHA pattern match raises a dashed warning banner: "This step may be blocked by a CAPTCHA … automation keeps retrying and the step will fail in ~N min", with "Pause run & take over" and "Dismiss — let it retry". A heuristic pause has no configured predicate, so hand-back stays manual and resumes by retrying the blocked step; if still blocked, the step fails → run failed/step_failed with the CAPTCHA diagnostic attached.

**Timeout.** Takeover countdown expiry → failed/takeover_timeout; the browser session closes and the pane shows "Session ended". **Cancel** is available while waiting and during takeover → cancelled; completed steps keep their results, the rest are skipped.

**Timeline.** The run timeline renders control as distinct colored intervals — automation (blue), waiting-for-you (amber striped), you-in-control (purple), verifying (teal) — with event markers: paused, you took control, control returned, resumed. The pause-for-takeover step in the step list shows "Completed by you · verified ✓" afterward.

This verdict feeds the backend + workers + live run area spec, together with apx4rs (live run view — its embedded browser pane is this pane).
