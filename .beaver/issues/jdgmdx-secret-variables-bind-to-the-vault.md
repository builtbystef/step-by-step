---
id: jdgmdx
title: Secret Variables bind to the vault
state: todo
priority: medium
depends_on:
    - 3679bv
    - z8p5dp
parent: 54i6da
created: 2026-08-14T06:15:21Z
updated: 2026-08-26T05:26:56Z
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
