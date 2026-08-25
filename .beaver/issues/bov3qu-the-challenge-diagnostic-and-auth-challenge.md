---
id: bov3qu
title: The challenge diagnostic and auth_challenge
state: done
assignee: agent
priority: medium
depends_on:
    - 6ewr2p
    - 1q7qp8
parent: 9gea5p
created: 2026-08-14T07:43:49Z
updated: 2026-08-25T19:56:04Z
---

## What to build

The classification that separates "the site fought back" from "the workflow broke". The Worker raises a `suspected_challenge` diagnostic when both hold: a Step has been resolving for at least 50% of its timeout, and the page carries a known challenge signal — an iframe whose host matches a small built-in provider list (reCAPTCHA, hCaptcha, Cloudflare Turnstile/challenges) or a well-known challenge container. The list is a constant in the Worker, not user-configurable, not extensible at runtime.

The diagnostic streams as a `diagnostic` event (the UI's dismissible banner feeds on it) and is attached to the Step Result's diagnostics if that Step ultimately fails — which is what turns the Run's `failure_reason` from `step_failed` into `auth_challenge`, the classification that routes a failed session transfer to a login Step or a takeover rather than a guessing heuristic. It never pauses a Run by itself: no heuristic takes control away from the user's own judgment.

## Acceptance criteria

- [ ] A fixture page embedding a challenge-provider iframe on a Step that stalls past half its timeout → one `suspected_challenge` diagnostic event naming the Step.
- [ ] The same stall on a page with no challenge signal → no diagnostic (the time condition alone is not enough).
- [ ] A challenge iframe present while the Step resolves quickly → no diagnostic (the signal condition alone is not enough).
- [ ] When the flagged Step then fails → the Run is `failed` / `auth_challenge`, and the diagnostic is on the Step Result.
- [ ] When the flagged Step eventually succeeds → the Run continues normally and the failure classification is untouched.
- [ ] The diagnostic alone never changes the Run's status — the Run keeps running until the Step resolves or fails.

## Notes

**agent** — 2026-08-25T19:45:33Z

Seam: the Worker executor against Playwright fixture pages (parent spec seam 2). Diagnostic events, Step Result diagnostics, and failure_reason are observed on the in-memory ResultStore the existing executor harness already records. The provider list and container selectors stay a Worker constant.

**agent** — 2026-08-25T19:56:04Z

Done. Challenge diagnostic and auth_challenge classification.

- Worker constant: recaptcha.net, hcaptcha.com, challenges.cloudflare.com iframe hosts, plus a small set of well-known containers (.g-recaptcha, .h-captcha, .cf-turnstile, Cloudflare challenge form/stage ids).
- During resolve, once a Step has used 50% of its timeout and the page shows a signal, one diagnostic event is emitted naming the Step. Time alone or signal alone is not enough.
- If that Step fails, the diagnostic is stored on the Step Result and the Run ends failed / auth_challenge. If it succeeds, the Run continues and failure_reason is untouched. The diagnostic never changes Run status by itself.
- Seam: executor browser tests against fixture pages (challenge.html, challenge-late.html). Postgres store now persists StepOutcome.diagnostics.
