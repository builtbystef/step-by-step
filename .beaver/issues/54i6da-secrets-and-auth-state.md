---
id: 54i6da
title: Secrets and Auth State
state: todo
labels:
    - spec
depends_on:
    - 7o0nmx
    - u7nkwh
created: 2026-08-11T20:54:02Z
updated: 2026-08-11T20:54:02Z
---

# Secrets and Auth State

## Problem Statement

Almost every workflow worth automating starts behind a login. That leaves a user with two things they must hand the tool and cannot afford to have leak: passwords, and the signed-in browser state they already have in their own Chrome. Both are bearer credentials — anything holding them can act as the user — and both pass through more hands than any other data in the system: an extension reads them, Postgres stores them, a Worker types them into a hostile web page, and screenshots, traces, and log lines are being captured the whole time. The user needs to store a password once and reuse it across Workflows, to carry a login from the browser where they recorded into the headless browser that replays weeks later, and to never see either turn up somewhere they did not put it.

## Solution

Two entities, each encrypted at rest under a master key that only the backend container ever holds. A **Secret** is a named value in a per-user vault; a Workflow's secret Variable points at one, so rotating a password is one edit in one place. An **Auth State** is the user's signed-in state for one site, captured from their Chrome with an explicit per-domain opt-in at recording save, injected into every Run's fresh browser, and refreshed by the Worker whenever a Run succeeds or a human hands control back after logging in by hand. Workers never get the master key: at Run start a Worker fetches the plaintext for that Run alone over an internal endpoint, and everything that leaves it afterwards — log lines, traces, step payloads — is stripped of those values on the way out.

## User Stories

1. As a user, I want to store a password once under a name and point several Workflows at it, so that a password change is one edit rather than a hunt.
2. As a user, I want to enter a recorded password at the moment I save the recording, so that the Workflow I just recorded is runnable without a second errand.
3. As a user, I want to reveal a stored value on the secrets page after re-entering my account password, so that I can check what I stored without that being an invitation to anyone holding my laptop.
4. As a user, I want to rename a Secret without breaking the Workflows bound to it, so that tidying the vault is safe.
5. As a user, I want deleting a Secret to warn me which Workflows use it, so that I do not break automation silently.
6. As a user, I want to be asked, per site, whether to save the login I just used while recording, so that nothing about my sessions is stored without my saying so.
7. As a user, I want my saved logins injected into every Run automatically, so that a scheduled Run at 3 a.m. starts signed in with no configuration.
8. As a user, I want a login I refresh by hand during a takeover to be kept, so that the same CAPTCHA or MFA prompt does not greet me on the next Run.
9. As a user, I want a Run that fails never to overwrite a good saved login, so that one bad Run does not cost me the session.
10. As a user, I want my passwords never to appear in a log line, a trace, or a step's stored payload, so that reading a Run's own output is not a way to read my credentials.
11. As a user, I want the browser recording to stop capturing while I am typing an MFA code during takeover, so that no screenshot preserves it.
12. As a user, I want to see and forget my saved logins per site, so that I can revoke what the tool holds.
13. As an operator, I want the instance to refuse to start without a valid master key, so that the failure is at boot rather than at the first secret.
14. As an operator, I want a CLI command that rotates the master key, so that a leaked key is recoverable without dumping and reloading the database.

## Implementation Decisions

### The two entities

**Secret** — a named encrypted value in a per-user vault. Name is unique per user. Lifecycle is stable: it changes when the user changes it.

**Auth State** — a user's signed-in browser state for one site, keyed by **registrable domain** (eTLD+1), unique per user and domain. One record for `example.com` holds cookies whose domain falls within it plus web storage for each origin visited under it, because logins routinely straddle `www.`, `app.`, and `accounts.` hosts of one site. Lifecycle is churning: sites expire it, Workers refresh it.

They are never interchangeable. A Secret is typed into a field by a Step; an Auth State is loaded into a browser context before the first navigation.

### Encryption and keys (ADR 0003)

App-level envelope encryption with **PyNaCl** (`SecretBox`, XSalsa20-Poly1305) on both levels:

- each record gets a fresh 32-byte data key; the plaintext is sealed under it;
- the data key is sealed under the master key;
- the row stores both sealed blobs (each carries its own nonce). Postgres never sees plaintext or an unwrapped data key.

The master key is base64 of 32 bytes in `STEPBYSTEP_MASTER_KEY`, supplied as a compose secret or environment variable. **The backend refuses to start** if it is absent, not valid base64, or not 32 bytes — a boot failure, never a first-use failure. Losing it makes every stored value unrecoverable, by design.

**The Worker containers never receive the master key.** This is a deliberate exception to `px25yw`'s "Workers reach Postgres directly" rule, recorded as ADR 0004. Workers are the containers that host hostile web content; a compromised Worker that held the key would decrypt every user's vault, whereas one that must ask the backend gets only the Runs it executes.

### Vault (web app)

One Settings area with two sections: **Secrets** and **Saved logins** (Auth State in user-facing words).

Secrets section — a list of name, last updated, and "used by N workflows" with the Workflow names. Create takes a name and a value. Edit changes name, value, or both; renaming never breaks a binding (see below). Delete shows the referencing Workflows in the confirmation and then proceeds — no blocking delete, no zombie Secrets; a Run whose bound Secret is gone fails at start with `missing_secret`.

**Reveal** is a two-stage unlock. The user re-enters their account password once, opening a **5-minute reveal window** on the current session; within it, each value can be revealed individually and **re-masks after 30 seconds**. The reveal window lives on the session row, so signing out or "sign out everywhere" closes it. There is no reveal for Auth State — a session blob has nothing a human can read usefully and everything an onlooker can steal.

Saved logins section — a list of domain, when it was saved, and a per-row "Forget this login". Forgetting has no cascade and no warning: future Runs start signed out and recover through a login Step or a takeover.

### Variable binding

A Workflow's secret Variable carries a pointer to the vault entry, separate from the Variable's own name. The Variable name stays readable in step text (`{{password}}` in every Workflow) while the vault keeps one flat namespace of distinguishable names (`acme-portal-password`). The pointer is the Secret's **id**, with its name cached beside it for display, so a rename never breaks a Version and a deleted Secret still yields a name to show in the `missing_secret` failure.

This refines `VariableBinding` in the Draft/Version document defined by the recording spec (d8ux2s):

```
VariableBinding = {
  name: string,          // what {{name}} references inside step values
  secret: boolean,
  secretId?: uuid,       // set iff secret; the vault entry this binds to
  secretName?: string    // cached for display; never authoritative
}
```

### Capture (extension)

At recording save, the extension lists **every distinct registrable domain the recording navigated to**, each with an **unchecked** checkbox: "Save your login for `example.com`? Future runs will start already signed in." No signed-in heuristic filters the list — a session cannot be reliably detected from outside, and a wrong filter silently hides the option the user wanted. Where a record already exists, the row reads "replaces the login saved on 3 Aug" and is still unchecked. Nothing is captured for an unchecked domain.

What a checked domain captures:

- **cookies** via `chrome.cookies` (including `httpOnly`, and each cookie's `secure`, `sameSite`, and partition key);
- **localStorage** and **sessionStorage** per origin, read by a content script in the recorded frames — the service worker cannot reach either.

`sessionStorage` is included because some sites keep the access token there, and a login that transfers *almost* is the worst failure this feature has.

A new Secret can also be created from the recording save screen: the value goes straight to the backend over the recording-scoped credential and never enters the step buffer. Binding to an existing Secret is a pick-from-list.

### Injection

At Run start the Worker fetches its Run's credentials and creates the browser context with **all of the user's Auth State records** loaded — not a subset computed from the Version's URLs. Static domain analysis is wrong exactly where it matters: navigate URLs carry `{{variable}}` interpolation resolved per Run, and SSO bounces through an identity-provider domain that appears in no Step. Inside the browser, cookies stay origin-isolated, so unrelated records are not exposed to the sites a Workflow visits, and the browser is exclusive to that one Run and destroyed after it.

Mechanically: cookies and `localStorage` go in through Playwright's storage state at context creation; `sessionStorage` is seeded per origin through an init script that runs before page scripts.

Secret values are fetched once, at Run start, and held in Worker memory for the Run's duration — which the settled `missing_secret`-at-start rule requires anyway.

### Write-back

The Worker browser is ephemeral; the Auth State store is the only cross-run carrier. Write-back happens at exactly two moments:

- **a Run succeeds**, and
- **a takeover hands back** — a human-refreshed login persists even if the Run later fails.

**A failed Run never writes back.** Its state may be poisoned (bot challenge, half-completed login) and would overwrite a known-good session.

Write-back **refreshes existing records only**. A domain the Run signed into that has no record is not stored — that would be keeping a bearer credential the user never consented to. The one path to a new record outside recording is takeover consent: at hand-back the Worker reports the registrable domains that gained a session and have no record; the run detail offers "keep this login for `site.com`?"; a consented domain is included in the next write-back. If the Run reaches a terminal state with the prompt unanswered, **nothing is stored** — no pending or provisional blob anywhere. The next Run asks again.

Concurrent same-user same-domain Runs are **last-write-wins**, accepted: no locks, no freshness stamps. The worst case is one extra login or takeover on the next Run.

Records have **no TTL**. A record lives until write-back overwrites it or the user forgets it. A site's real session lifetime is invisible to us, so any expiry we picked would delete good sessions and keep dead ones; a stale record simply fails to authenticate, and the Workflow's login Step or a takeover recovers.

### Leak prevention

- **Stored form** — step payloads and Step Results carry the Variable name only, never a value (d8ux2s).
- **Log lines** — redaction happens **in the Worker, before anything is published to Redis**: every secret value bound to that Run is substring-replaced with `••••` in log lines, error strings, and failure detail. **No minimum length.** A three-character secret shredding the user's own logs is a better failure than a three-character secret appearing in them.
- **Traces** — Playwright trace capture is bracketed around every secret-referencing Step (`stop_chunk` before, `start_chunk` after). The trace has a hole, not a password.
- **Screenshots are not suppressed.** Password fields mask themselves and that is accepted.
- **Takeover** — during a `waiting_for_human` interval the live stream continues (the user is watching themselves) but periodic screenshots and trace capture pause, resuming at hand-back. A screenshot must never catch an MFA code mid-type.
- **Backend** — the credentials endpoint's response body is excluded from request logging; no plaintext ever reaches a log sink.
- **Auth State blobs are never rendered** in the UI in any form.

### HTTP API contract

User-facing, session cookie, under the one app origin:

```
GET    /api/secrets                    → 200 [{id, name, updated_at,
                                               used_by: [{workflow_id, workflow_name}]}]
POST   /api/secrets      {name, value} → 201 {id, name}
                                         409 code=name_taken
PATCH  /api/secrets/{id} {name?, value?} → 200 {id, name}
                                         409 code=name_taken
DELETE /api/secrets/{id}               → 204

POST   /api/secrets/unlock  {password} → 204, opens a 5-minute reveal window on this session
                                         401 code=bad_credentials
POST   /api/secrets/{id}/reveal        → 200 {value}
                                         403 code=reveal_locked

GET    /api/auth-states                → 200 [{id, domain, created_at, updated_at}]
DELETE /api/auth-states/{id}           → 204

POST   /api/runs/{runId}/auth-state-consents  {domain} → 204
                                         404 code=not_a_candidate
```

Extension, over the recording-scoped credential minted by `POST /api/workflows/{id}/recording-sessions` (d8ux2s):

```
POST /api/recording-sessions/{sessionId}/secrets     {name, value} → 201 {id, name}
POST /api/recording-sessions/{sessionId}/auth-states
  { captures: [ AuthStateBlob ] }                                  → 204   // upsert per domain
```

Internal, Worker → backend, authenticated by a shared token from the compose environment; every route additionally requires that `runId` names a Run **currently assigned to a Worker and in a non-terminal state**:

```
GET  /internal/runs/{runId}/credentials
     → 200 { secrets:    [{variable_name, value}],
             authStates: [ AuthStateBlob ] }
     → 409 code=missing_secret {variable_names: [string]}

GET  /internal/runs/{runId}/auth-state-consents
     → 200 { domains: [string] }        // new domains the user approved during takeover

POST /internal/runs/{runId}/auth-states
     { states: [ AuthStateBlob ], new_candidates: [string] }
     → 204
     → 400 code=unconsented_domain {domain}   // a state for a domain with neither an
                                              // existing record nor consent is rejected,
                                              // never silently dropped
```

The blob shape, shared by capture, injection, and write-back:

```
AuthStateBlob = {
  domain: string,                        // registrable domain (eTLD+1)
  cookies: Cookie[],                     // Playwright/Chrome cookie shape, incl. httpOnly,
                                         // secure, sameSite, partition key
  origins: [{ origin: string,
              local_storage: [{name, value}] }],
  session_storage: [{ origin: string,
                      items: [{name, value}] }]
}
```

The Worker calls `auth-state-consents` immediately before its final write-back, so a domain the user approved seconds after hand-back is still caught. An unconsented blob never leaves the Worker.

### CLI contract

One command in the backend container, beside the account CLI (ufnuvx):

```
rotate-master-key     re-wraps every Secret's and Auth State's data key from
                      STEPBYSTEP_MASTER_KEY to STEPBYSTEP_NEW_MASTER_KEY.
                      Record plaintexts are never decrypted or rewritten.
                      Per record it tries the current key, then the new one, so a
                      re-run after a partial failure completes rather than corrupts.
                      Prints re-wrapped and already-rotated counts.
```

The operator swaps the environment variables afterwards and restarts the backend.

### Schema (shape, not migration)

- `secrets`: id, user_id, name (unique per user), sealed_value, sealed_data_key, created_at, updated_at.
- `auth_states`: id, user_id, domain (unique per user), sealed_blob, sealed_data_key, created_at, updated_at.
- `sessions` (ufnuvx) gains one additive column: reveal_unlocked_until.
- `runs` gains the takeover write-back candidates and the user's consents — a small table or JSONB column keyed by run and domain, discarded with the Run's row.

Both entities are already covered by the account-deletion cascade in ufnuvx.

## Dependencies

- **PyNaCl** — libsodium bindings for `SecretBox`; the encryption primitive ADR 0003 chose. Python's standard library has no AEAD.
- **A public-suffix list** (`publicsuffix2` or equivalent) — registrable-domain computation is the Auth State key, and eTLD+1 cannot be derived by string splitting (`example.co.uk`, `foo.github.io`).

Nothing else. Cookie and storage capture use existing Chrome extension APIs; injection uses Playwright, already in the Workers.

## Testing Decisions

Two seams.

**1. Backend HTTP API**, tests speaking HTTP to the FastAPI app with a real Postgres — the same seam the other two specs use. It covers the vault, the reveal window, extension capture, the internal Run endpoints, write-back consent, and redaction (the Worker-side publish helper is driven directly and the result asserted on the backend's SSE stream — one path, no separate module seam).

Worked examples:

- `POST /api/secrets` twice with one name → 201 then 409 `name_taken`; the same name under a second user → 201.
- Rename a Secret bound to a published Version → the Version still runs, and `GET /internal/runs/{id}/credentials` returns the value under the unchanged Variable name.
- Delete a Secret bound to a Workflow → 204, and a Run of that Workflow → 409 `missing_secret` naming the Variable.
- `POST /api/secrets/{id}/reveal` with no unlock → 403 `reveal_locked`; after `unlock` with the right password → 200 with the value; the same call 6 minutes later → 403; after `logout-all` → 403.
- `unlock` with a wrong password → 401 and no window opens.
- Capture two domains from a recording session → two `auth_states` rows; re-capture one → the same row id with new content and an unchanged created_at.
- A Run whose user has records for `a.com` and `b.com`, executing a Version that only names `a.com` → `credentials` returns both (the inject-all rule, observable).
- Write-back naming a domain with no record and no consent → 400 `unconsented_domain`, and no row appears.
- The same domain after `POST /api/runs/{id}/auth-state-consents` → 204 and a new row; the consent listed by `GET /internal/runs/{id}/auth-state-consents` beforehand.
- A Run that reaches `failed` → no write-back is accepted for it at all (the endpoint's non-terminal-state check fires).
- Internal endpoints without the shared token → 401; with the token but a terminal Run → 409.
- A log line containing a Run's secret value, published through the Worker helper → arrives over SSE with `••••` and no fragment of the value; a two-character secret is redacted too.
- Delete an account holding Secrets and Auth State (ufnuvx's cascade) → both tables are empty for that user.

**2. The envelope-encryption module**, tested directly. This is the one place where "it silently produced garbage" is both unacceptable and invisible from outside.

Worked examples: seal then open under the same master key → the original bytes; a flipped byte in the sealed value → an authentication error, never partial plaintext; the same plaintext sealed twice → different ciphertexts (fresh data key and nonce); open under a wrong master key → an error, not garbage; `rotate-master-key` over a table of N records → every record still opens under the new key, none under the old, plaintexts byte-identical; the rotation re-run against an already-rotated table → zero re-wrapped, N already-rotated, no corruption; a malformed `STEPBYSTEP_MASTER_KEY` → the process refuses to start.

Prior art: none in the repository yet — the accounts spec (ufnuvx) lands the HTTP test harness and Postgres fixtures this reuses, and the recording spec (d8ux2s) lands the extension harness that capture tests extend.

## Out of Scope

- Cloud KMS integration (7o0nmx, ADR 0003) — v1 is an env-supplied master key.
- Per-workflow secret values (7o0nmx) — Secrets live in a user-level vault and Workflows bind to them.
- Per-domain locks or freshness stamps for write-back (7o0nmx) — last-write-wins.
- Suppressing screenshots on secret-referencing Steps (7o0nmx) — trace bracketing covers it.
- Silent Auth State export from the extension (7o0nmx) — capture is always an explicit per-domain opt-in.
- Reveal for Auth State, and any audit log of reveals or vault changes.
- Per-Worker credentials for the internal endpoints — a fixed compose pool has no provisioning step to hang them on.
- TLS between Worker and backend; they share the compose network and Workers are never internet-facing (px25yw).
- Automatic capture of any domain a Run signs into, outside takeover consent.
- Expiry, refresh-ahead, or health-checking of stored Auth State.
- The run detail's rendering of the "keep this login?" prompt and of takeover intervals — the execution area's spec (kvz5sv) owns that surface; this spec owns the data and the endpoints behind it.
- Secret and Variable *editing* UI inside the workflow editor — d8ux2s owns the Variables drawer; this spec adds only the vault picker it reads from.

## Further Notes

- **Touches two published specs.** ufnuvx's `sessions` table gains `reveal_unlocked_until`; d8ux2s's `VariableBinding` gains `secretId` and `secretName`. Both are additive and neither has been implemented yet.
- **ADR 0004** records the Workers-never-hold-the-master-key exception to px25yw's direct-Postgres model; write it with this spec's first slice.
- `u7nkwh` established what breaks a transferred session: Entra device-bound PRT cookies, Token Binding, Cloudflare `cf_clearance` bound to a visitor, HUMAN device fingerprinting. **No source supports a population rate for any of these**, so v1 predicts nothing — a transfer that fails is a classified auth/challenge failure that routes to a login Step or a takeover. Do not add heuristics that guess.
- Cookie partitioning (CHIPS) and separate cookie stores mean an origin-wide export can be incomplete; capture the partition key and pass it through, and expect surprises on sites using partitioned cookies in iframes.
- Playwright's storage state does not carry `sessionStorage`; the init-script seeding is the reason `sessionStorage` is a separate field on the blob rather than folded into `origins`.
- Glossary terms this spec leans on: Secret, Auth State, Variable, Worker, Run, Step Result, Artifact — all already defined.
