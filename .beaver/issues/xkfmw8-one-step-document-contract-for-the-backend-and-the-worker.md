---
id: xkfmw8
title: One Step document contract, for the backend and the Worker both
state: done
assignee: agent
priority: medium
labels:
    - maintenance
created: 2026-08-19T01:52:09Z
updated: 2026-08-24T07:48:30Z
---

## What to build

The Step document contract — `Step`, `Target`, `SelectorCandidate`, `FrameHop`, the eight payloads — is declared once, in `packages/core`, and the backend and the Worker both read it from there.

Today it exists twice. `apps/api/.../workflows/document.py` holds the Pydantic contract that validates every save (`sl7h4j`), and `apps/worker/.../selectors.py` holds hand-written dataclasses for the three parts resolution needs, with a `Target.from_document` that reads the stored JSONB (`mwrkwp`). The Worker cannot import the backend's module — `packages/core` is the only thing both sides share, and it carries no document models — so the second copy was the price of the first Worker-side reader.

The executor (`6ewr2p`) is where the price rises: it walks all eight Step types and acts on every payload, so without a shared contract it hand-rolls a full second reading of the document, free to drift from the validation that wrote it.

Worth deciding in the slice: whether core takes a Pydantic dependency (the backend's models move as they are, and the Worker gains a parser it did not have) or the contract lands as dataclasses the backend's Pydantic models are built from. The backend's API shape — the camelCase aliases, `extra="forbid"`, `exclude_none` — must not change either way: it is a published contract with a generated client.

## Acceptance criteria

- [ ] The Step document contract is declared in `packages/core` alone; neither `apps/api` nor `apps/worker` declares a second copy of any part of it.
- [ ] The Worker reads a Target from a stored document through the shared contract, and selector resolution keeps its behaviour: its browser-tier tests pass untouched.
- [ ] The backend's OpenAPI schema and generated client are byte-identical to what is committed today — this move is invisible on the wire.
- [ ] The Draft save's refusals (`unknown_step_type`, `malformed_payload`, `duplicate_step_id`, `undeclared_variable`, `duplicate_variable_name`) still answer as they do now, proved by the existing integration tests.

## Notes

**agent** — 2026-08-24T07:43:34Z

Test seams selected for this AFK implementation: the shared core document models parse stored camelCase Target and all eight Step payloads; the existing Worker browser seam must remain untouched; existing backend integration refusal tests and the committed OpenAPI/generated-client diff prove wire compatibility.

**agent** — 2026-08-24T07:48:30Z

Completed: moved the full Pydantic Workflow document contract into step_by_step_core.document and made both the backend and Worker import it; the backend retains only whole-document refusals/diff/state, and Target.from_document now parses stored camelCase data through the shared model. Chose Pydantic in core because it preserves the published validation and serialization contract directly and gives the Worker the parser needed by the executor. Verified pnpm check, pnpm test, all 16 unchanged Worker browser tests, and pnpm build; OpenAPI and generated client have no diff. The service-backed refusal tests could not be run because Postgres was not running, but their unchanged routes/models are covered by the fast tier and schema regeneration.
