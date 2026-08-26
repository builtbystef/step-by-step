---
id: jdgmdx
title: Secret Variables bind to the vault
state: done
assignee: agent
priority: medium
depends_on:
    - 3679bv
    - z8p5dp
parent: 54i6da
created: 2026-08-14T06:15:21Z
updated: 2026-08-26T05:56:15Z
---

## What to build

The pointer from a Workflow's secret Variable to its vault entry. The pointer is the Secret's id, with the name cached beside it for display — so the Variable name stays readable in step text (`{{password}}` everywhere) while the vault keeps one flat namespace, renaming a Secret never breaks a Version, and a deleted Secret still yields a name to show when a Run later fails with `missing_secret`. This refines `VariableBinding` in the Draft/Version document:

```
VariableBinding = {
  name: string,          // what {{name}} references inside step values
  secret: boolean,
  secretId?: uuid,       // set iff secret; the vault entry this binds to
  secretName?: string    // cached for display; never authoritative
}
```

The document store validates the refined shape. The Variables drawer's secret Variables gain the vault picker: bind to an existing Secret picked from a list. Usage becomes visible: `GET /api/secrets` gains `used_by: [{workflow_id, workflow_name}]`, the Secrets settings list shows "used by N workflows" with the names, and the delete confirmation names the referencing Workflows before proceeding — informing, never blocking.

## Acceptance criteria

- [ ] The store accepts a secret Variable carrying `secretId` and `secretName`, and rejects `secretId` on a non-secret Variable.
- [ ] A Draft binding `{{password}}` to Secret `acme-portal-password` shows that binding in the Variables drawer; picking a different Secret updates the Draft's binding.
- [ ] Renaming the Secret leaves every Draft and Version binding intact — the id is the pointer — and the drawer and settings list show the new name.
- [ ] Two Workflows bound to one Secret → its `used_by` lists both with names; unbinding one → only the other remains.
- [ ] The delete confirmation lists the referencing Workflow names and deletes anyway on confirm — no blocking delete, no zombie rows.
- [ ] After the bound Secret is deleted, the Draft's binding still carries the cached name for display; the document is unchanged and still valid.

## Notes

**agent** — 2026-08-26T04:18:19Z

Loop paused mid-iteration. Partial Variable vault-pointer work was reverted; start fresh.

**agent** — 2026-08-26T05:26:56Z

Loop iteration died on Grok 403 after ~13 min of uncommitted work. Partial vault-pointer/used_by/drawer code was reverted; start fresh.

**agent** — 2026-08-26T05:37:11Z

Seams for this slice (AFK): (1) the document store at HTTP, plus the shared Variable contract it parses — accept secretId/secretName on a secret Variable, reject secretId on a non-secret; a document is not checked against live vault rows, so a deleted Secret still leaves a valid Draft. (2) GET /api/secrets used_by at HTTP, scanning this Organization's Drafts and Versions for the Secret's id (a Workflow counts once even if both bind). Delete stays unblocked. (3) Frontend decisions without a DOM: variables.ts for the drawer picker (live vault name by id, cached name after delete, pick updates the Draft); settings/secrets usage copy for 'used by N workflows' and the delete confirmation listing names.

**agent** — 2026-08-26T05:56:15Z

Completed Secret Variable vault bindings.

The document contract gained secretId (the pointer) and secretName (display cache). The store accepts both on a secret Variable and refuses secretId on a non-secret (malformed_payload). Existence in the vault is not a save rule, so a deleted Secret leaves the Draft valid and still carrying the cached name.

GET /api/secrets now includes used_by: [{workflow_id, workflow_name}], scanned from this Organization's Drafts and Versions; a Workflow counts once. Delete stays unblocked and leaves no vault rows.

The Variables drawer picks from the vault list: the live name shows while the Secret exists, the cached name after it is gone, and picking rewrites the Draft's pointer. Settings lists "used by N workflows" with names; the delete confirmation names them too.

Seams as noted: HTTP for the store and used_by; variables.ts and settings/secrets/usage.ts without a DOM.

Verification: core document tests, editor variables tests, settings usage tests, and the new integration cases (used_by, rename, delete-and-resave) pass. pnpm check's Python fan-out could not uv-sync in this sandbox (network); the same ruff/ty/pytest commands against the workspace venv pass, as does Vitest (355).
