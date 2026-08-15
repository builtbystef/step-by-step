---
id: 2aybf8
title: The pane and takeover UI
state: todo
priority: medium
depends_on:
    - tz0rix
    - 5yu03g
    - bov3qu
    - oul652
    - clxd1b
parent: 9gea5p
created: 2026-08-14T07:44:50Z
updated: 2026-08-14T07:44:50Z
---

## What to build

The cockpit's main pane becomes the Worker's actual browser, and takeover becomes something a person does. The noVNC client renders the VNC WebSocket in three states: view-only while automation runs ("view only — automation in control"), amber-highlighted while the Run waits, interactive during takeover. Around it:

- **The waiting card**: the reason (the pause Step's author-written message, or the pause request), the countdown, the success check's live state from `predicate` events, "take over browser", "cancel run".
- **The control bar** (purple, above the pane, during control): the identity of the controlled browser, the countdown turning red when low, "hand control back", "cancel run"; the success-check line beneath the pane, with the 6-second grace countdown and "hand back now" / "stay in control" when the check is met.
- **The unmet hand-back choice**: "keep control and finish it" or "give up — fail the run".
- **A second tab** of the same user gets a view-only pane and a note saying where control is held.
- **The challenge banner**: a dismissible banner on `diagnostic` events offering "pause run & take over".
- **The consent prompt**: at hand-back, "keep this login for site.com?" per reported candidate domain, calling the per-Run consent endpoint (the data and rules live in the secrets spec; this screen renders them).
- **Terminal**: the pane holds the final page with "session ended — the browser closed"; a timed-out takeover reports it.

## Acceptance criteria

- [ ] Watching a running Run shows live frames; clicks into the view-only pane change nothing on the page.
- [ ] When the Run parks, the pane turns amber and the waiting card shows the pause Step's message, the ticking countdown, and the check's live state flipping met/unmet with the page.
- [ ] "Take over browser" makes the same pane interactive — typing lands in the Worker's browser — with the control bar and countdown above it.
- [ ] With the check met during control, the grace countdown renders; "stay in control" keeps control and further met states do not hand back; "hand back now" resumes automation immediately.
- [ ] Hand-back with the check unmet presents the keep-control / give-up choice; give-up leads to the failed terminal banner with `takeover_abandoned`.
- [ ] A second tab shows view-only with the where-is-control note while the first holds control.
- [ ] A challenge diagnostic renders the dismissible banner; its "pause run & take over" parks the Run and opens the waiting card.
- [ ] A hand-back with a new-domain candidate shows the keep-this-login prompt, and consenting registers through the consent endpoint.
- [ ] On takeover timeout the pane reports the session ended and the banner shows `takeover_timeout`.
