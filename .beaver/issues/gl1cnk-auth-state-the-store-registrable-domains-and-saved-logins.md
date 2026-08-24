---
id: gl1cnk
title: 'Auth State: the store, registrable domains, and Saved logins'
state: done
assignee: agent
priority: medium
depends_on:
    - i1osfd
    - lac27w
    - hat4cf
parent: 54i6da
created: 2026-08-14T06:14:58Z
updated: 2026-08-24T07:34:52Z
---

## What to build

The Auth State entity and its user-facing management. An Auth State is signed-in browser state for one site, keyed by registrable domain (eTLD+1). One table holds both layers: `user_id NULL` is the Organization's record — at most one per domain per Organization — and `user_id` set is that member's Personal Override, at most one per member per domain, allowed even for a domain the Organization has no record for (a member's personal login for a site the org never saved is exactly the different-account use case). One record for `example.com` holds cookies whose domain falls within it plus web storage for each origin visited under it, because logins straddle `www.`, `app.`, and `accounts.` hosts. The whole blob is sealed with the envelope module as one value. Registrable-domain computation uses a public-suffix list; string splitting cannot derive it. The blob shape, shared later by capture, injection, and write-back:

```
AuthStateBlob = {
  domain: string,                        // registrable domain (eTLD+1)
  cookies: Cookie[],                     // Chrome/Playwright cookie shape incl. httpOnly,
                                         // secure, sameSite, partition key
  origins: [{ origin, local_storage: [{name, value}] }],
  session_storage: [{ origin, items: [{name, value}] }]
}
```

The read side, session cookie plus the `X-Organization` header:

```
GET    /api/auth-states      → 200 [{id, domain, scope: "organization"|"personal",
                                     created_at, updated_at}]
                               // org records + the caller's own personal records only
DELETE /api/auth-states/{id} → 204   // another member's personal record → 404
```

The Settings vault surface gains its second section, Saved logins: the Organization's records and the caller's own, each row showing domain, scope, when it was saved, and a per-row "Forget this login". Any member forgets an org record; a personal record only its holder. Forgetting has no cascade and no warning — future Runs start signed out and recover through a login Step or a takeover. Auth State blobs are never rendered in the UI in any form, and there is no reveal for them. Writes arrive with later slices (capture and write-back); this slice tests the store's upsert semantics directly.

## Acceptance criteria

- [ ] The registrable-domain module: `www.example.co.uk` and `app.example.co.uk` both key to `example.co.uk`; `foo.github.io` keys to `foo.github.io` (public-suffix rules, not string splitting).
- [ ] Uniqueness holds on both layers: storing a blob for an existing (org, domain) — or (org, member, domain) — replaces the content on the same row id with `created_at` unchanged and `updated_at` moved; the org layer's uniqueness is enforced even though its user_id is NULL (the partial unique index).
- [ ] A personal record can exist for a domain with no org record, and the two layers for one domain coexist as distinct rows.
- [ ] The stored row contains only sealed blobs; no cookie value appears in the table.
- [ ] GET lists the active Organization's records plus the caller's own personal ones — never another member's — with domain, scope, and timestamps; the response shape has no field that could carry blob contents.
- [ ] DELETE forgets the record and leaves other rows untouched; another member's personal record id → 404; another Organization's id → 404.
- [ ] Deleting the Organization leaves no rows; removing a member deletes that member's personal records and leaves the org layer intact.
- [ ] The Saved logins section lists both layers with domain, scope, and saved-date, with a per-row Forget that acts immediately, no cascade warning, personal rows shown only to their holder.

## Notes

**claude** — 2026-08-15T04:14:42Z

Re-scope per ADR 0005 before building: Auth State is org-scoped (unique per Organization and domain) with Personal Overrides per the note on 54i6da — a member's own signed-in state for a domain, used for Runs they start. Registrable-domain and blob-shape decisions are unchanged.

**agent** — 2026-08-24T07:34:52Z

Completed the Auth State slice: libpsl-backed registrable domains; the envelope-sealed two-layer store with stable upserts, partial Organization uniqueness, and Membership/Organization cascades; metadata-only list and scoped forget endpoints; generated API contract; and the Saved logins Settings surface with immediate per-row Forget. The blob contract preserves cookies (including extension fields), per-origin local storage, and session storage. Used the platform libpsl dependency rather than a Python PSL package so the deployed image and host use the maintained public-suffix implementation. Added direct domain tests, real-Postgres store/API/cascade tests, and Saved-login wording coverage. pnpm check, pnpm test, and pnpm build pass.
