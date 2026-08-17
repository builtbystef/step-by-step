---
id: clxd1b
title: 'Run credentials: the internal endpoints and takeover consent'
state: todo
priority: medium
depends_on:
    - jdgmdx
    - gl1cnk
    - 423dg6
parent: 54i6da
created: 2026-08-14T06:16:00Z
updated: 2026-08-17T04:04:08Z
---

## What to build

The backend side of the Worker's credential path — the seam that lets Workers act without ever holding the master key (ADR 0004), and the place where Personal Override resolution lives. Internal routes authenticate with a shared token from the compose environment, and every route additionally requires that the Run is currently assigned to a Worker and in a non-terminal state. The shapes are resolution-blind — Workers never learn that overrides exist:

```
GET  /internal/runs/{runId}/credentials
     → 200 { secrets:    [{variable_name, value}],     // resolved per the Run's starter
             authStates: [ AuthStateBlob ] }           // the resolved, per-domain-merged set
     → 409 code=missing_secret {variable_names: [string]}

GET  /internal/runs/{runId}/auth-state-consents
     → 200 { domains: [string] }        // consented new domains; destination is backend state

POST /internal/runs/{runId}/auth-states
     { states: [ AuthStateBlob ], new_candidates: [string] }
     → 204
     → 400 code=unconsented_domain {domain}
```

Resolution is one rule: a Run started by a member resolves each secret Variable through the starter's Personal Override first, then the org Secret, and the injected Auth State set is the union over domains — the starter's personal record wins per domain, org records fill the rest, personal-only domains included. Scheduled and Batch Runs resolve org values only. The resolving identity is fixed at Run start; a takeover by another member does not re-resolve. `credentials` returns the plaintext for every secret Variable of the Run's Version and **all** applicable Auth States — never a subset computed from the Version's URLs, because navigate URLs interpolate variables per Run and SSO bounces through domains no Step names.

Write-back routing re-applies the same rule per domain: a domain the starter holds a personal record for refreshes the personal record; otherwise an existing org record refreshes; Scheduled and Batch Runs refresh org records only. A state for a domain with neither an existing record at the resolved destination nor a consent is rejected, never silently dropped. `new_candidates` records domains that gained a session during takeover and have no record; the user answers through the public per-Run consent endpoint, choosing the destination — on a Scheduled or Batch Run only the Organization option exists:

```
POST /api/runs/{runId}/auth-state-consents  {domain, scope}
     → 204 | 404 code=not_a_candidate | 422 code=no_starter   // scope=personal, no starter
```

A `personal`-scoped consent creates the record for the **consenting** member. Candidates and consents (domain, scope, consenting member) live with the Run's row and are discarded with it — no pending or provisional blob anywhere. The credentials response body is excluded from request logging; no plaintext ever reaches a log sink.

This slice's edge on the execution spec is an umbrella; tighten it to the specific execution slices when that spec is sliced.

## Acceptance criteria

- [ ] Internal routes without the shared token → 401; with the token but a terminal or unassigned Run → 409.
- [ ] An Organization with records for `a.com` and `b.com`, and a starter holding personal `a.com` and `c.com`, running a Version that names only `a.com` → `credentials` returns the starter's `a.com`, the org's `b.com`, and the starter's `c.com` (resolution and the inject-all rule, both observable).
- [ ] A member with a Personal Override on a bound Secret starts a Run → `credentials` carries the override's value; a Scheduled Run of the same Workflow → the org value; a Run another member starts → the org value.
- [ ] After renaming a bound Secret, `credentials` returns the value under the unchanged Variable name.
- [ ] A Run whose bound Secret was deleted → 409 `missing_secret` naming the Variable (an override cannot outlive its Secret).
- [ ] `POST /api/workflows/{id}/runs` for a Workflow whose Version binds a deleted Secret → 409 `missing_secret` with the Variable names, and no Run is created (the start-time check the execution contract promises).
- [ ] Write-back after a member-started Run refreshes the starter's personal row where one exists and the org row otherwise; the untargeted layer is byte-identical; the same Workflow on a Schedule refreshes the org row.
- [ ] Write-back naming a domain with no record and no consent → 400 `unconsented_domain`, and no row appears.
- [ ] The same domain after consent with `scope: organization` → 204 and a new org row; with `scope: personal` → a new personal row for the consenting member; the consent was visible in `GET auth-state-consents` beforehand.
- [ ] Consent for a domain never reported as a candidate → 404 `not_a_candidate`; `scope: personal` on a Scheduled or Batch Run → 422 `no_starter`.
- [ ] A Run that reached `failed` → write-back is rejected by the non-terminal check, so a failed Run's state can never land.
- [ ] The credentials response body appears in no request log line.

## Notes

**claude** — 2026-08-17T04:04:08Z

Two pins. (1) The run detail (GET /api/runs/{id}) gains auth_state_candidates: [{domain, consent: {scope} | null}] — populated from this slice's candidate/consent state, empty when the Run has none; 2aybf8's keep-this-login prompt renders it. (2) missing_secret precedence (mirrored on 423dg6): the request-time 409 on POST .../runs is a best-effort pre-check; this slice's 409 at the credentials fetch is authoritative for every trigger — a Run whose Secret disappears between start and claim ends failed/missing_secret.
