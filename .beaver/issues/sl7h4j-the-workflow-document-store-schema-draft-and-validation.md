---
id: sl7h4j
title: 'The Workflow document store: schema, Draft, and validation'
state: todo
priority: high
depends_on:
    - h9gene
    - lac27w
parent: d8ux2s
created: 2026-08-14T06:01:49Z
updated: 2026-08-17T04:03:47Z
---

## What to build

The storage model everything else in this spec writes into. A Workflow row carries exactly one owner, a name, a workflow-level default step timeout (30 s, stored explicitly — never inherited from a library default), and a takeover timeout (30 min default). Its single mutable Draft and each future Version store one self-contained JSONB document holding `steps` and `variables`. Draft read and save routes exist, with the full Step-document validation at save time. A minimal create route (name only) exists so a Draft can exist at all; the full list/search/rename/delete/duplicate contract is the app-shell spec's ground. The document contract:

```
Step = { id: uuid, type: navigate|click|type|select|download|extract|wait|pause-for-takeover,
         label, optional, disabled, screenshot?: boolean (default false),
         timeoutMs?, payload per type }
Target = { candidates: ranked SelectorCandidate[], frame?, unsupported?: {reason, warning} }
SelectorCandidate = { kind: testid|role|placeholder|label|alt|text|title|css, value, shadowPath? }
pause-for-takeover payload = { message?, timeoutMs?, successCheck?: Target }
type/navigate values allow {{name}} interpolation mixing freely with literal text
extract payload = scalar (one named value, text or attribute) | list (flat records of
                  sub-selector fields — no nesting)
```

## Acceptance criteria

- [ ] Creating a Workflow stores owner, name, and both timeouts with their defaults written explicitly; an empty Draft document exists from creation.
- [ ] The Draft is read and saved as one document; save replaces it whole; per-type payload changes need no migration.
- [ ] Validation accepts all eight step types with their payloads, the `screenshot` flag, and `successCheck` on pause-for-takeover; an unknown type or malformed payload is rejected with a machine-readable error.
- [ ] Step ids are app-minted UUIDs and never rewritten: a save keeps every id exactly as submitted.
- [ ] A save whose step array contains a duplicate id is rejected, and the error names the duplicated id.
- [ ] A save where a step value references `{{name}}` that `variables` does not declare is rejected — this is how deleting a still-used Variable is refused at the seam.
- [ ] Tenancy holds: another user's Workflow or Draft is 404, never 403-with-existence-leak.
- [ ] HTTP seam tests with a real Postgres cover the duplicate-id example, the undeclared-variable refusal, id stability, and isolation.

## Notes

**claude** — 2026-08-17T04:03:47Z

Tenancy wording per ADR 0005: 'another user's Workflow or Draft is 404' reads 'another Organization's' — Workflows are org-owned and any member of the Organization reads and saves the Draft. Pinned Draft routes (this slice owns them): GET /api/workflows/{id}/draft → 200 {steps, variables}; PUT /api/workflows/{id}/draft {steps, variables} → 200 replacing the document whole, 400 with machine-readable codes on validation failure (duplicate_step_id naming the id, undeclared_variable naming the name, unknown_step_type, malformed_payload). Every route carries an operation_id — the generated client is named from it.
