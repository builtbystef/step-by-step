---
id: qf8loh
title: Worker injection and write-back
state: todo
priority: medium
depends_on:
    - clxd1b
    - 6ewr2p
    - qmnvgr
parent: 54i6da
created: 2026-08-14T06:16:13Z
updated: 2026-08-14T07:45:35Z
---

## What to build

The Worker side of the credential path. At Run start the Worker fetches its Run's credentials once and holds them in memory for the Run's duration. The Worker is override-ignorant: the backend hands it an already-resolved set (the starter's Personal Overrides folded in for member-started Runs) and routes each written-back domain to the right record — nothing on this side distinguishes an org value from an override. The browser context is created with every returned Auth State loaded: cookies and localStorage through Playwright's storage state, sessionStorage seeded per origin by an init script that runs before page scripts — storage state cannot carry it, which is why the blob keeps it as a separate field. Origin isolation inside the browser keeps unrelated records invisible to the sites a Workflow visits; the browser is exclusive to the one Run and destroyed after it.

Write-back happens at exactly two moments: when a Run succeeds, and when a takeover hands back — a human-refreshed login persists even if the Run later fails. A failed Run never writes back; its state may be poisoned (bot challenge, half-completed login) and would overwrite a known-good session. Write-back refreshes existing records and includes takeover-consented new domains; the Worker calls the consents endpoint immediately before its final write-back, so a consent given seconds after hand-back is still caught. An unconsented blob never leaves the Worker; if the Run reaches a terminal state with the prompt unanswered, nothing is stored and the next Run asks again. Concurrent Runs writing the same record are last-write-wins — no locks, no freshness stamps — and records have no TTL.

This slice's edge on the execution spec is an umbrella; tighten it when that spec is sliced.

## Acceptance criteria

- [ ] A Run starts signed in with no login Step: a Version asserting the seeded test site's signed-in state passes, with the saved cookies, localStorage, and sessionStorage all present before the first navigation.
- [ ] Seeded sessionStorage is visible to the page's own scripts on first load.
- [ ] A successful Run refreshes the stored record: `updated_at` moves and the new session content is stored.
- [ ] A failed Run leaves the stored record byte-identical.
- [ ] A takeover hand-back writes back even when the Run later fails — the human-refreshed login is kept.
- [ ] A new domain signed into during takeover: consented before the Run ends → stored in the final write-back; never consented → absent everywhere once the Run is terminal.
- [ ] Secrets are fetched once at start: deleting a bound Secret mid-Run does not affect the running Run, and the next Run fails at start with `missing_secret`.
