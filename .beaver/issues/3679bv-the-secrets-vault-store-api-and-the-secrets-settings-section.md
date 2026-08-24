---
id: 3679bv
title: 'The Secrets vault: store, API, and the Secrets settings section'
state: done
assignee: agent
priority: high
depends_on:
    - i1osfd
    - lac27w
    - hat4cf
parent: 54i6da
created: 2026-08-14T06:14:44Z
updated: 2026-08-24T06:49:22Z
---

## What to build

The Organization's Secret vault, with the member's personal layer. A Secret is a named encrypted value — name unique per Organization — sealed with the envelope module; the row stores the sealed value and its sealed data key, nothing readable. A member may keep a Personal Override on a Secret: their own value, sealed identically in its own row, with no name of its own — invisible to every account but its holder. The user-facing API, session cookie plus the `X-Organization` header:

```
GET    /api/secrets                      → 200 [{id, name, updated_at,
                                                 my_override: {updated_at} | null}]
POST   /api/secrets      {name, value}   → 201 {id, name} | 409 code=name_taken
PATCH  /api/secrets/{id} {name?, value?} → 200 {id, name} | 409 code=name_taken
DELETE /api/secrets/{id}                 → 204   // cascades every member's override

POST   /api/secrets/{id}/reveal          → 200 {value}   // the org value; ungated
PUT    /api/secrets/{id}/override {value} → 204          // the caller's own
DELETE /api/secrets/{id}/override        → 204
POST   /api/secrets/{id}/override/reveal → 200 {value} | 404 code=no_override
```

Reveal is deliberately ungated — any signed-in member, per-click, no re-authentication (passwordless auth removed the credential a sudo gate would ask for, and any member can exfiltrate through a Run anyway); the revealed value re-masks after 30 seconds as a UI courtesy, not a boundary.

And the first half of the Settings vault surface: a Secrets section listing name and last-updated, with create (name and value), edit (name, value, or both), delete behind a confirmation, per-row reveal with the 30-second re-mask, and the caller's own layer — "Use my own value" to set or update an override, a marker with its date when one exists, and a clear action. Deleting never blocks and leaves no zombie rows.

Deliberately deferred: the used-by column, the Workflow names inside the delete confirmation, and the `used_by` field on the list response arrive with the vault-binding slice.

## Acceptance criteria

- [ ] `POST /api/secrets` twice with one name in one Organization → 201 then 409 `name_taken`; the same name in a second Organization → 201.
- [ ] A stored value's row contains only sealed blobs — no fragment of the plaintext appears in the table; the same holds for override rows.
- [ ] Renaming via PATCH keeps the value; PATCH with a new value re-seals it and moves `updated_at`.
- [ ] DELETE returns 204, the row is gone, and every member's override on it is gone; deleting again → 404.
- [ ] Every endpoint scopes to the active Organization: a member of another Organization hitting the id — and the right id under the wrong `X-Organization` — → 404.
- [ ] Reveal signed in, no other ceremony → 200 with the plaintext; signed out → 401.
- [ ] PUT override then GET list → `my_override` set for the caller and null for another member of the same Organization; override reveal returns the caller's value while plain reveal still returns the org value; DELETE override → `no_override` on the next override reveal.
- [ ] Deleting the Organization leaves no rows in the secrets or overrides tables — the org-deletion cascade covers both.
- [ ] The Settings → Secrets section lists name and last-updated, creates, renames, edits the value, deletes behind a confirmation, reveals with a 30-second re-mask, and sets/clears the caller's own value with a visible marker.

## Notes

**claude** — 2026-08-15T04:14:42Z

Re-scope per ADR 0005 before building: the vault is per-Organization, not per-user (name unique per Organization, org_id on the row, X-Organization on the API), plus Personal Overrides per the note on 54i6da. The envelope encryption and API shape are otherwise unchanged.

**agent** — 2026-08-24T06:49:22Z

Completed the Organization-scoped Secret vault end to end: added cascading Secret and Personal Override tables, envelope-sealed CRUD/reveal/override API routes with tenant-hidden ids and name conflict handling, the generated OpenAPI client, and the Settings → Secrets create/edit/delete/reveal/override surface with a 30-second re-mask. Added HTTP-seam integration coverage for every backend criterion and a UI policy test for the reveal duration. Updated the architecture record. Verification: pnpm check, pnpm test, and pnpm build pass; the service-backed integration file was not run because Postgres is not running in this harness.
