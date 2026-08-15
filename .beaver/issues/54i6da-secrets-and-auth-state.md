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
updated: 2026-08-15T04:31:44Z
---

# Secrets and Auth State

> Revised 2026-08-15 for ADR 0005: the vault is the Organization's, Personal Overrides exist, reveal is ungated, and captures choose their destination. The revision note at the bottom records the decisions.

## Problem Statement

Almost every workflow worth automating starts behind a login. That leaves an Organization with two things its members must hand the tool and cannot afford to have leak: passwords, and the signed-in browser state they already have in their own Chrome. Both are bearer credentials — anything holding them can act as the account they belong to — and both pass through more hands than any other data in the system: an extension reads them, Postgres stores them, a Worker types them into a hostile web page, and screenshots, traces, and log lines are being captured the whole time. An Organization needs to store a password once and reuse it across Workflows, to carry a login from the browser where a member recorded into the headless browser that replays weeks later, and to never see either turn up somewhere it was not put. And because members sometimes must run the same Workflow signed in as *themselves* — their own account sees different data — a member needs a way to lay their own credential over the shared one without touching what everyone else, and every Schedule, uses.

## Solution

Two entities in an Organization's vault, each encrypted at rest under a master key that only the backend container ever holds, plus one member-scoped layer over them. A **Secret** is a named value in the Organization's vault; a Workflow's secret Variable points at one, so rotating a password is one edit in one place. An **Auth State** is the Organization's signed-in state for one site, captured from a member's Chrome with an explicit per-domain opt-in at recording save, injected into every Run's fresh browser, and refreshed by the Worker whenever a Run succeeds or a human hands control back after logging in by hand. A **Personal Override** is a member's own value for either — their password for a Secret, their login for a domain — resolved in place of the shared value for Runs that member starts, while Scheduled and Batch Runs keep using the Organization's values. Workers never get the master key and never learn that overrides exist: at Run start a Worker fetches the already-resolved plaintext for that Run alone over an internal endpoint, and everything that leaves it afterwards — log lines, traces, step payloads — is stripped of those values on the way out.

## User Stories

1. As a member, I want to store a password once under a name and point several of my Organization's Workflows at it, so that a password change is one edit rather than a hunt.
2. As a member, I want to enter a recorded password at the moment I save the recording, so that the Workflow I just recorded is runnable without a second errand.
3. As a member, I want to reveal a stored value on the secrets page, so that I can check what I stored.
4. As a member, I want to rename a Secret without breaking the Workflows bound to it, so that tidying the vault is safe.
5. As a member, I want deleting a Secret to warn me which Workflows use it, so that I do not break automation silently.
6. As a member, I want to be asked, per site, whether to save the login I just used while recording — and whether it is for the Organization or just for me — so that nothing about my sessions is stored without my saying so, and my personal account never silently becomes the Organization's.
7. As a member, I want to keep my own value for a Secret or my own login for a site, so that Runs I start use my account and see my data while Schedules keep using the Organization's.
8. As a member, I want saved logins injected into every Run automatically, so that a scheduled Run at 3 a.m. starts signed in with no configuration.
9. As a member, I want a login I refresh by hand during a takeover to be kept, so that the same CAPTCHA or MFA prompt does not greet me on the next Run.
10. As a member, I want a Run that fails never to overwrite a good saved login, so that one bad Run does not cost the Organization the session.
11. As a member, I want passwords never to appear in a log line, a trace, or a step's stored payload, so that reading a Run's own output is not a way to read credentials.
12. As a member, I want the browser recording to stop capturing while I am typing an MFA code during takeover, so that no screenshot preserves it.
13. As a member, I want to see and forget the Organization's saved logins per site — and my own — so that I can revoke what the tool holds.
14. As an operator, I want the instance to refuse to start without a valid master key, so that the failure is at boot rather than at the first secret.
15. As an operator, I want a CLI command that rotates the master key, so that a leaked key is recoverable without dumping and reloading the database.

## Implementation Decisions

### The two entities, and the Personal Override

**Secret** — a named encrypted value in an Organization's vault. Name is unique per Organization. Lifecycle is stable: it changes when a member changes it. A member may keep a **Personal Override** on a Secret: their own value, sealed the same way, with no name of its own — the org Secret carries the name and the Variable bindings; the override only substitutes the value.

**Auth State** — signed-in browser state for one site, keyed by **registrable domain** (eTLD+1). The Organization holds at most one record per domain, and each member may additionally hold their own **Personal Override** record per domain — including for a domain the Organization has no record for, because a member's personal login for a site the org never saved is exactly the different-account use case. One record for `example.com` holds cookies whose domain falls within it plus web storage for each origin visited under it, because logins routinely straddle `www.`, `app.`, and `accounts.` hosts of one site. Lifecycle is churning: sites expire it, Workers refresh it.

Secrets and Auth State are never interchangeable. A Secret is typed into a field by a Step; an Auth State is loaded into a browser context before the first navigation.

### Resolution at Run time

One rule, applied wholly in the backend:

- A Run **started by a member** resolves through that member's overrides first. Each secret Variable takes the starter's override value if one exists, else the org Secret's value. The injected Auth State set is the union over domains: the starter's personal record wins per domain, org records fill the remaining domains, and a personal-only domain is injected too.
- **Scheduled and Batch Runs** resolve the Organization's values only. Overrides never apply — there is no member to apply.
- The resolving identity is fixed at Run start. A takeover by a different member does not re-resolve mid-Run.
- Workers are override-ignorant: the internal credentials endpoint returns the resolved plaintext, and nothing in the Worker's contract distinguishes an org value from an override.

### Encryption and keys (ADR 0003)

App-level envelope encryption with **PyNaCl** (`SecretBox`, XSalsa20-Poly1305) on both levels:

- each record gets a fresh 32-byte data key; the plaintext is sealed under it;
- the data key is sealed under the master key;
- the row stores both sealed blobs (each carries its own nonce). Postgres never sees plaintext or an unwrapped data key.

Personal Overrides are sealed identically — every sealed row in the system, org or personal, participates in the same envelope scheme and the same rotation.

The master key is base64 of 32 bytes in `STEPBYSTEP_MASTER_KEY`, supplied as a compose secret or environment variable. **The backend refuses to start** if it is absent, not valid base64, or not 32 bytes — a boot failure, never a first-use failure. Losing it makes every stored value unrecoverable, by design.

**The Worker containers never receive the master key.** This is a deliberate exception to `px25yw`'s "Workers reach Postgres directly" rule, recorded as ADR 0004. Workers are the containers that host hostile web content; a compromised Worker that held the key would decrypt every vault, whereas one that must ask the backend gets only the Runs it executes.

### Vault (web app)

One Settings area with two sections — **Secrets** and **Saved logins** (Auth State in user-facing words) — scoped to the active Organization via the `X-Organization` header like every other domain surface. Every member has full vault access: create, edit, delete, reveal. Roles do not partition the vault; a member who can run Workflows already handles what the vault protects.

Secrets section — a list of name, last updated, and "used by N workflows" with the Workflow names. Create takes a name and a value. Edit changes name, value, or both; renaming never breaks a binding (see below). Delete shows the referencing Workflows in the confirmation and then proceeds — no blocking delete, no zombie Secrets; a Run whose bound Secret is gone fails at start with `missing_secret`. Deleting a Secret deletes every member's override on it.

Each row also carries the caller's own layer: **Use my own value** sets or updates the caller's Personal Override; a marker shows when the caller has one, with its own updated-date and a clear action. Nobody sees anyone else's overrides — not even the owner; an override is invisible to every account but its holder.

**Reveal is ungated.** Any signed-in member reveals a value per-click, and it re-masks after 30 seconds — a UI courtesy against onlookers, not a security boundary. There is no re-authentication step: passwordless auth removed the natural sudo credential, and a gate would be theater anyway — any member can exfiltrate a value by running a Workflow that types it somewhere visible. A member's own override reveals the same way. There is no reveal for Auth State — a session blob has nothing a human can read usefully and everything an onlooker can steal.

Saved logins section — the Organization's records and the caller's personal records, each row showing domain, scope (the Organization's login / your login), when it was saved, and a per-row "Forget this login". Any member forgets an org record; a personal record is forgotten only by its holder. Forgetting has no cascade and no warning: future Runs start signed out and recover through a login Step or a takeover.

### Variable binding

A Workflow's secret Variable carries a pointer to the vault entry, separate from the Variable's own name. The Variable name stays readable in step text (`{{password}}` in every Workflow) while the vault keeps one flat namespace of distinguishable names (`acme-portal-password`). The pointer is the Secret's **id**, with its name cached beside it for display, so a rename never breaks a Version and a deleted Secret still yields a name to show in the `missing_secret` failure. Overrides are invisible to the document: a binding never references one — substitution happens at resolution.

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

At recording save, the extension lists **every distinct registrable domain the recording navigated to**, each with an **unchecked** checkbox: "Save your login for `example.com`? Future runs will start already signed in." No signed-in heuristic filters the list — a session cannot be reliably detected from outside, and a wrong filter silently hides the option the user wanted. A checked row exposes a **destination choice**: *for the Organization* (the default) or *just for me* — the member's Personal Override. Where a record already exists at the chosen destination, the row reads "replaces the login saved on 3 Aug" (or "replaces your login saved on 3 Aug") and is still unchecked. Nothing is captured for an unchecked domain.

What a checked domain captures:

- **cookies** via `chrome.cookies` (including `httpOnly`, and each cookie's `secure`, `sameSite`, and partition key);
- **localStorage** and **sessionStorage** per origin, read by a content script in the recorded frames — the service worker cannot reach either.

`sessionStorage` is included because some sites keep the access token there, and a login that transfers *almost* is the worst failure this feature has.

A new Secret can also be created from the recording save screen: the value goes straight to the backend over the recording-scoped credential and never enters the step buffer. The save screen creates **org Secrets only** — a binding must point at one; a member who wants their own value sets the override afterwards in Settings. Binding to an existing Secret is a pick-from-list.

### Injection

At Run start the Worker fetches its Run's credentials and creates the browser context with **the whole resolved Auth State set** loaded — every org record plus, for a member-started Run, the starter's personal records, personal winning per domain — never a subset computed from the Version's URLs. Static domain analysis is wrong exactly where it matters: navigate URLs carry `{{variable}}` interpolation resolved per Run, and SSO bounces through an identity-provider domain that appears in no Step. Inside the browser, cookies stay origin-isolated, so unrelated records are not exposed to the sites a Workflow visits, and the browser is exclusive to that one Run and destroyed after it.

Mechanically: cookies and `localStorage` go in through Playwright's storage state at context creation; `sessionStorage` is seeded per origin through an init script that runs before page scripts.

Secret values are fetched once, at Run start, and held in Worker memory for the Run's duration — which the settled `missing_secret`-at-start rule requires anyway.

### Write-back

The Worker browser is ephemeral; the Auth State store is the only cross-run carrier. Write-back happens at exactly two moments:

- **a Run succeeds**, and
- **a takeover hands back** — a human-refreshed login persists even if the Run later fails.

**A failed Run never writes back.** Its state may be poisoned (bot challenge, half-completed login) and would overwrite a known-good session.

**The backend routes each domain's refresh** by re-applying the resolution rule at write-back time: a domain the starter holds a personal record for refreshes the personal record; otherwise an existing org record refreshes the org record; Scheduled and Batch Runs refresh org records only. The Worker posts blobs by domain and knows nothing about where they land. Re-resolving at write-back rather than remembering the injection-time answer means a mid-Run override change can shift the target — accepted, in the same spirit as last-write-wins.

Write-back otherwise **refreshes existing records only**. A domain the Run signed into that has no record is not stored — that would be keeping a bearer credential nobody consented to. The one path to a new record outside recording is takeover consent: at hand-back the Worker reports the registrable domains that gained a session and have no record; the run detail offers "keep this login for `site.com`?" with the same destination choice as capture — *for the Organization* or *just for me* (the consenting member's own record; on a Scheduled or Batch Run only the Organization option exists, there being no starter to attach a personal record to). A consented domain is included in the next write-back and stored at the consented destination. If the Run reaches a terminal state with the prompt unanswered, **nothing is stored** — no pending or provisional blob anywhere. The next Run asks again.

Concurrent Runs writing the same record are **last-write-wins**, accepted: no locks, no freshness stamps. The worst case is one extra login or takeover on the next Run.

Records have **no TTL**. A record lives until write-back overwrites it or a member forgets it. A site's real session lifetime is invisible to us, so any expiry we picked would delete good sessions and keep dead ones; a stale record simply fails to authenticate, and the Workflow's login Step or a takeover recovers.

### Leak prevention

- **Stored form** — step payloads and Step Results carry the Variable name only, never a value (d8ux2s).
- **Log lines** — redaction happens **in the Worker, before anything is published to Redis**: every secret value resolved for that Run — org values and Personal Overrides alike — is substring-replaced with `••••` in log lines, error strings, and failure detail. **No minimum length.** A three-character secret shredding the user's own logs is a better failure than a three-character secret appearing in them.
- **Traces** — Playwright trace capture is bracketed around every secret-referencing Step (`stop_chunk` before, `start_chunk` after). The trace has a hole, not a password.
- **Screenshots are not suppressed.** Password fields mask themselves and that is accepted.
- **Takeover** — during a `waiting_for_human` interval the live stream continues (the user is watching themselves) but periodic screenshots and trace capture pause, resuming at hand-back. A screenshot must never catch an MFA code mid-type.
- **Backend** — the credentials endpoint's response body is excluded from request logging; no plaintext ever reaches a log sink.
- **Auth State blobs are never rendered** in the UI in any form.

### HTTP API contract

User-facing, session cookie plus the `X-Organization` header, under the one app origin:

```
GET    /api/secrets                    → 200 [{id, name, updated_at,
                                               used_by: [{workflow_id, workflow_name}],
                                               my_override: {updated_at} | null}]
POST   /api/secrets      {name, value} → 201 {id, name}
                                         409 code=name_taken
PATCH  /api/secrets/{id} {name?, value?} → 200 {id, name}
                                         409 code=name_taken
DELETE /api/secrets/{id}               → 204   // cascades every member's override

POST   /api/secrets/{id}/reveal        → 200 {value}           // the org value; ungated
PUT    /api/secrets/{id}/override {value} → 204                // the caller's own
DELETE /api/secrets/{id}/override      → 204
POST   /api/secrets/{id}/override/reveal → 200 {value}
                                         404 code=no_override

GET    /api/auth-states                → 200 [{id, domain, scope: "organization"|"personal",
                                               created_at, updated_at}]
                                         // org records + the caller's personal records only
DELETE /api/auth-states/{id}           → 204   // another member's personal record → 404

POST   /api/runs/{runId}/auth-state-consents  {domain, scope} → 204
                                         404 code=not_a_candidate
                                         422 code=no_starter   // scope=personal on a
                                                               // Scheduled or Batch Run
```

Every id is resolved inside the active Organization; a foreign Organization's id is a 404, never a 403.

Extension, over the recording-scoped credential minted by `POST /api/workflows/{id}/recording-sessions` (d8ux2s) — the session knows its Workflow's Organization and its recording member, so `personal` scope needs no extra identity:

```
POST /api/recording-sessions/{sessionId}/secrets     {name, value} → 201 {id, name}
POST /api/recording-sessions/{sessionId}/auth-states
  { captures: [ { ...AuthStateBlob, scope: "organization"|"personal" } ] } → 204
  // upsert per (domain, destination)
```

Internal, Worker → backend, authenticated by a shared token from the compose environment; every route additionally requires that `runId` names a Run **currently assigned to a Worker and in a non-terminal state**. The shapes are resolution-blind — nothing here mentions overrides:

```
GET  /internal/runs/{runId}/credentials
     → 200 { secrets:    [{variable_name, value}],     // resolved per the Run's starter
             authStates: [ AuthStateBlob ] }           // the resolved, per-domain-merged set
     → 409 code=missing_secret {variable_names: [string]}

GET  /internal/runs/{runId}/auth-state-consents
     → 200 { domains: [string] }        // consented new domains; destination is backend state

POST /internal/runs/{runId}/auth-states
     { states: [ AuthStateBlob ], new_candidates: [string] }
     → 204                              // backend routes each domain per the resolution rule
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

One command in the backend container (the container's CLI entry point lands with the rotation slice):

```
rotate-master-key     re-wraps every sealed row's data key — Secrets, Auth States, and
                      Personal Overrides of both — from STEPBYSTEP_MASTER_KEY to
                      STEPBYSTEP_NEW_MASTER_KEY. Record plaintexts are never decrypted
                      or rewritten. Per record it tries the current key, then the new
                      one, so a re-run after a partial failure completes rather than
                      corrupts. Prints re-wrapped and already-rotated counts.
```

The operator swaps the environment variables afterwards and restarts the backend.

### Schema (shape, not migration)

- `secrets`: id, org_id, name (unique per Organization), sealed_value, sealed_data_key, created_at, updated_at.
- `secret_overrides`: id, secret_id (FK, cascade on Secret delete), user_id, sealed_value, sealed_data_key, created_at, updated_at; unique (secret_id, user_id).
- `auth_states`: id, org_id, user_id (**NULL = the Organization's record**; set = that member's Personal Override), domain, sealed_blob, sealed_data_key, created_at, updated_at; unique per (org_id, user_id, domain) with the NULL case enforced by a partial unique index.
- `runs` gains the takeover write-back candidates and consents — domain, scope, and the consenting member — a small table or JSONB column keyed by run, discarded with the Run's row.

Cascades: Organization deletion purges the whole vault (jrp1pq); removing a member — or their account's deletion — deletes their overrides in that Organization (o99b7t owns the domain-effects slice); deleting a Secret cascades its overrides.

## Dependencies

- **PyNaCl** — libsodium bindings for `SecretBox`; the encryption primitive ADR 0003 chose. Python's standard library has no AEAD.
- **A public-suffix list** (`publicsuffix2` or equivalent) — registrable-domain computation is the Auth State key, and eTLD+1 cannot be derived by string splitting (`example.co.uk`, `foo.github.io`).

Nothing else. Cookie and storage capture use existing Chrome extension APIs; injection uses Playwright, already in the Workers.

## Testing Decisions

Two seams.

**1. Backend HTTP API**, tests speaking HTTP to the FastAPI app with a real Postgres — the same seam the other specs use. It covers the vault, overrides and resolution, extension capture, the internal Run endpoints, write-back routing and consent, and redaction (the Worker-side publish helper is driven directly and the result asserted on the backend's SSE stream — one path, no separate module seam).

Worked examples:

- `POST /api/secrets` twice with one name in one Organization → 201 then 409 `name_taken`; the same name in a second Organization → 201.
- A member of another Organization hitting the secret's id with GET, PATCH, DELETE, or reveal → 404; the right id under the wrong `X-Organization` → 404.
- `POST /api/secrets/{id}/reveal` signed in, no other ceremony → 200 with the value; signed out → 401.
- Rename a Secret bound to a published Version → the Version still runs, and `GET /internal/runs/{id}/credentials` returns the value under the unchanged Variable name.
- Delete a Secret bound to a Workflow → 204, its overrides are gone, and a Run of that Workflow → 409 `missing_secret` naming the Variable.
- A member sets an override on a Secret → a Run **they** start resolves the override's value; a Scheduled Run of the same Workflow resolves the org value; a Run another member starts resolves the org value.
- `my_override` on the list reflects only the caller: member A with an override and member B without see different values for the same Secret.
- Auth State union: the org holds `a.com` and `b.com`, the starter holds personal `a.com` and `c.com` → `credentials` returns the starter's `a.com`, the org's `b.com`, and the starter's `c.com`.
- Capture two domains from a recording session, one `organization` and one `personal` → an org row and a personal row for the recording member; re-capturing one → the same row id with new content and an unchanged created_at.
- Write-back after a successful member-started Run where the starter holds a personal record for the domain → the personal row is refreshed and the org row is byte-identical; the same Workflow on a Schedule → the org row is refreshed.
- Write-back naming a domain with no record and no consent → 400 `unconsented_domain`, and no row appears.
- The same domain after `POST /api/runs/{id}/auth-state-consents` with `scope: organization` → 204 and a new org row; with `scope: personal` → a new personal row for the consenting member; `scope: personal` on a Scheduled Run → 422 `no_starter`.
- A Run that reaches `failed` → no write-back is accepted for it at all (the endpoint's non-terminal-state check fires).
- Internal endpoints without the shared token → 401; with the token but a terminal Run → 409.
- A log line containing a Run's resolved secret value — an override included — published through the Worker helper → arrives over SSE with `••••` and no fragment of the value; a two-character secret is redacted too.
- Removing a member from the Organization (o99b7t's cascade) → their overrides are gone and the org rows remain; deleting the Organization (jrp1pq's cascade) → every vault table is empty for that org.

**2. The envelope-encryption module**, tested directly. This is the one place where "it silently produced garbage" is both unacceptable and invisible from outside.

Worked examples: seal then open under the same master key → the original bytes; a flipped byte in the sealed value → an authentication error, never partial plaintext; the same plaintext sealed twice → different ciphertexts (fresh data key and nonce); open under a wrong master key → an error, not garbage; `rotate-master-key` over a table of N records — overrides included → every record still opens under the new key, none under the old, plaintexts byte-identical; the rotation re-run against an already-rotated table → zero re-wrapped, N already-rotated, no corruption; a malformed `STEPBYSTEP_MASTER_KEY` → the process refuses to start.

Prior art: none in the repository yet — the accounts spec (ufnuvx) lands the HTTP test harness and Postgres fixtures this reuses, and the recording spec (d8ux2s) lands the extension harness that capture tests extend.

## Out of Scope

- Cloud KMS integration (7o0nmx, ADR 0003) — v1 is an env-supplied master key.
- Per-workflow secret values (7o0nmx) — Secrets live in the Organization's vault and Workflows bind to them.
- Per-domain locks or freshness stamps for write-back (7o0nmx) — last-write-wins.
- Suppressing screenshots on secret-referencing Steps (7o0nmx) — trace bracketing covers it.
- Silent Auth State export from the extension (7o0nmx) — capture is always an explicit per-domain opt-in.
- Re-authentication before reveal (sudo mode) — the password it would have asked for no longer exists (ADR 0005), and a gate would be theater when any member can exfiltrate through a Run; revisit only if a hosted tier demands it.
- Any audit log of reveals or vault changes, and any admin visibility into which members hold overrides.
- Role-based partitioning of the vault — every member has full vault access.
- Reveal for Auth State.
- Per-Worker credentials for the internal endpoints — a fixed compose pool has no provisioning step to hang them on.
- TLS between Worker and backend; they share the compose network and Workers are never internet-facing (px25yw).
- Automatic capture of any domain a Run signs into, outside takeover consent.
- Expiry, refresh-ahead, or health-checking of stored Auth State.
- The run detail's rendering of the "keep this login?" prompt and of takeover intervals — the execution area's spec (kvz5sv) owns that surface; this spec owns the data and the endpoints behind it.
- Secret and Variable *editing* UI inside the workflow editor — d8ux2s owns the Variables drawer; this spec adds only the vault picker it reads from.

## Further Notes

- **Touches one published spec.** d8ux2s's `VariableBinding` gains `secretId` and `secretName` — additive, not yet implemented. (The revision removed the old sessions-table touch: with reveal ungated there is no reveal window and no `reveal_unlocked_until` column.)
- **ADR 0004** records the Workers-never-hold-the-master-key exception to px25yw's direct-Postgres model; write it with this spec's first slice.
- **Workers are override-ignorant by design.** Resolution and write-back routing live entirely in the backend; if a future feature needs the Worker to distinguish org from personal state, that is a contract change to the internal API, not a Worker patch.
- `u7nkwh` established what breaks a transferred session: Entra device-bound PRT cookies, Token Binding, Cloudflare `cf_clearance` bound to a visitor, HUMAN device fingerprinting. **No source supports a population rate for any of these**, so v1 predicts nothing — a transfer that fails is a classified auth/challenge failure that routes to a login Step or a takeover. Do not add heuristics that guess.
- Cookie partitioning (CHIPS) and separate cookie stores mean an origin-wide export can be incomplete; capture the partition key and pass it through, and expect surprises on sites using partitioned cookies in iframes.
- Playwright's storage state does not carry `sessionStorage`; the init-script seeding is the reason `sessionStorage` is a separate field on the blob rather than folded into `origins`.
- Glossary terms this spec leans on: Secret, Auth State, Personal Override, Organization, Membership, Variable, Worker, Run, Step Result, Artifact — all already defined.

## Notes

**claude** — 2026-08-15T04:14:42Z

ADR 0005 (2026-08-15) re-scopes this spec's tenancy: the vault belongs to the Organization, not the user. Secrets and Auth State become org-scoped (org_id replaces user_id; names/domains unique per Organization) with a new entity, the Personal Override — a member's own value for a Secret or Auth State, used for Runs that member starts (glossary has all three terms). Run-time resolution to settle when this spec is revised: a member-started Run resolves the runner's Personal Override first, then the org value; Scheduled and Batch Runs use the org values. Removal from the Organization and account deletion delete that member's overrides (see o99b7t). This spec needs a revision pass before its sub-issues are built — labeled needs-review.

**claude** — 2026-08-15T04:31:44Z

Revision applied 2026-08-15, settling the ADR 0005 questions: (1) reveal is ungated — any signed-in member, no re-auth (the account password it required no longer exists); the unlock window, /api/secrets/unlock, and the sessions reveal_unlocked_until column are gone, and c635m7 is cancelled with the reveal endpoint folded into 3679bv. (2) Every capture point (recording save, takeover consent) carries an explicit destination choice: for the Organization or just for me. (3) Resolution: member-started Runs use the starter's Personal Overrides first; Scheduled/Batch Runs use org values; the backend resolves and routes write-back — Workers stay override-ignorant. Schema: secrets.org_id, secret_overrides (secret_id, user_id), auth_states with nullable user_id (NULL = org record).
