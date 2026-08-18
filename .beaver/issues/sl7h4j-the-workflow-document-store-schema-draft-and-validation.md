---
id: sl7h4j
title: 'The Workflow document store: schema, Draft, and validation'
state: done
assignee: claude
priority: high
depends_on:
    - h9gene
    - lac27w
parent: d8ux2s
created: 2026-08-14T06:01:49Z
updated: 2026-08-18T10:35:09Z
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

**claude** — 2026-08-18T10:35:09Z

Done. The Workflow document store, its two Draft routes, and the org-context dependency every later domain route will use.

**What landed**

- `apps/api/.../workflows/models.py` — `workflows` (org-owned, `default_step_timeout_ms` 30 000 and `takeover_timeout_ms` 1 800 000 written into the INSERT, not left to a library default) and `workflow_drafts` (one JSONB `document` per Workflow, created empty with the Workflow). Migration `1be493f219da`.
- `workflows/document.py` — the document contract. The eight Step types are a Pydantic union discriminated by `type`, so the generated TypeScript client hands the editor a tagged union; `validated()` holds the two whole-document rules (no repeated Step id, no `{{name}}` the document does not declare).
- `workflows/routes.py` — `POST /api/workflows` (name only, 201), `GET`/`PUT /api/workflows/{id}/draft`, all with `operation_id`s. `DocumentRoute` turns FastAPI's 422 into this application's `{code, message}`, so the Draft routes speak one dialect: `unknown_step_type`, `malformed_payload`, `duplicate_step_id`, `undeclared_variable`, all 400.
- `accounts/orgs.py` — `ActiveMembership`, the `X-Organization` dependency the accounts spec defines and no slice had yet built.

**Decisions**

- **The Step document is the one camelCase part of the API.** The spec pins `timeoutMs`, `outputName`, `subSelector`, `successCheck` as the contract at the API and recorder seams, and the recorder and the editor both write it in JavaScript. Everything else on the wire — including the Workflow resource itself — stays snake_case.
- **A field nobody set is left out, not written as `null`.** Absence is what optional means in this document, and a save that read back with a hundred added nulls would not be the document the editor sent. `response_model_exclude_none=True` on both Draft routes, `exclude_none` in what the column stores.
- **`extra="forbid"` on every document model.** A key nobody reads is a Step the recorder thinks it saved and the executor never acts on; the save is the cheap place to find that out.
- **`{{name}}` is interpolated in a navigate URL and a type value, and nowhere else**, per the spec's pinned contract, so those are the only two values scanned for undeclared references. A `{{` in a select value or a pause message is literal text.
- **`X-Organization` is optional in the OpenAPI schema and required at runtime.** The frontend's fetch wrapper sets it on every request, so a required parameter would make each generated call site pass what one interceptor already carries — and a missing header has to arrive as this app's error shape (400 `organization_required`) rather than as FastAPI's 422. An id that is not a UUID answers 403 `not_a_member`, the same as an Organization the caller is not in: which of the two it was would say which ids exist.
- **No `workflow_versions` table and no `updated_at` on `workflows`.** Versions are `g795ji`'s, with their own migration; an unmaintained last-activity column would be a bug waiting for the list screen (`5rkj33`) that computes it.
- **The migration was hand-finished.** Autogenerate also proposed dropping the `invitation_role` and `membership_role` check constraints — noise from SQLAlchemy's non-native `Enum`, deleted from the revision. Published as `t6xbdg`, and the architecture doc warns about it until that lands.

**Facts a reviewer needs**

- Seam: HTTP against the app with a real Postgres, as the spec's Testing Decisions name. Twelve tests in `tests/integration/test_workflows.py`; the tier is 33 passing.
- Mutation-checked, since two tenancy tests passed on arrival: dropping `Workflow.org_id == member.org_id` from the Draft lookup fails the 404 test, and dropping `Membership.user_id == user.id` from the org dependency fails the `not_a_member` test.
- The account scaffolding (`client`, `new_account`) moved into `tests/integration/conftest.py` for the domain tiers to share. `test_accounts.py` keeps its own helpers untouched — there the sign-in flow is the subject, not the setup.
- `pnpm run ci` green; `openapi.json` and the generated client are regenerated and committed.
- Left deliberately: a Draft may still declare the same Variable name twice, which is ambiguous for secret masking. No criterion covered it, so it is `aultl3` rather than a line in this diff.
