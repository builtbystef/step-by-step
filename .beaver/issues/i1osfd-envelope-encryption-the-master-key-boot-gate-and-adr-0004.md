---
id: i1osfd
title: Envelope encryption, the master-key boot gate, and ADR 0004
state: done
assignee: claude
priority: high
depends_on:
    - h9gene
parent: 54i6da
created: 2026-08-14T06:14:32Z
updated: 2026-08-18T07:53:36Z
---

## What to build

The encryption core every vault feature stands on, per ADR 0003: app-level envelope encryption with PyNaCl's SecretBox (XSalsa20-Poly1305) on both levels. Sealing a plaintext generates a fresh 32-byte data key, seals the plaintext under it, seals the data key under the master key, and returns both sealed blobs, each carrying its own nonce. Opening reverses it. Postgres never sees plaintext or an unwrapped data key. A re-wrap primitive re-seals a record's data key under a new master key without touching the plaintext, trying the current key first and then the new one, so a partially rotated table can be processed again safely.

The master key arrives as base64 of 32 bytes in `STEPBYSTEP_MASTER_KEY`, supplied as a compose secret or environment variable. The backend refuses to start when the variable is absent, not valid base64, or not 32 bytes — a boot failure, never a first-use failure. Losing the key makes every stored value unrecoverable, by design.

Write ADR 0004 with this slice: Worker containers never receive the master key — a deliberate exception to the execution architecture's Workers-reach-Postgres-directly rule. Workers host hostile web content; a compromised Worker holding the key would decrypt every Organization's vault, whereas one that must ask the backend gets only the Runs it executes.

## Acceptance criteria

- [ ] Seal then open under the same master key returns the original bytes.
- [ ] The same plaintext sealed twice produces different ciphertexts and different sealed data keys — a fresh data key and nonce every time.
- [ ] A single flipped byte in the sealed value or the sealed data key produces an authentication error, never partial plaintext.
- [ ] Opening under a wrong master key produces an error, not garbage.
- [ ] The re-wrap primitive moves a sealed record from one master key to another with the plaintext byte-identical afterwards; applied to an already re-wrapped record it reports it as already rotated and changes nothing.
- [ ] The backend process refuses to start when `STEPBYSTEP_MASTER_KEY` is missing, is not valid base64, or decodes to a length other than 32 bytes.
- [ ] ADR 0004 records that Workers never hold the master key, and why.

## Notes

**claude** — 2026-08-18T07:53:36Z

Built: `step_by_step_api.envelope` (the backend's alone — never in the Worker image, ADR 0004), the master-key boot gate in the app's lifespan, ADR 0004, and the compose/.env wiring.

Module surface, for the vault slices that build on it: `seal(plaintext, master) -> Sealed(value, data_key)`, `open_sealed(sealed, master) -> bytes`, `rewrap(sealed_data_key, current, new) -> bytes | None`, `master_key() -> bytes`, plus `KEY_BYTES`, `MASTER_KEY_VARIABLE`, and `MasterKeyError`.

Decisions made while building:

- **Every function takes the master key it works with**; only `master_key()` reads the environment (cached, `lru_cache(1)`). Rotation is inherently a two-key operation, so a module-global key would have needed a swap dance; this also lets the crypto tests run with keys of their own instead of monkeypatching the environment.
- **`rewrap` takes the sealed data key alone**, not the whole `Sealed`. "Without touching the plaintext" is then structurally true — the sealed value is never passed in. It returns `None` for an already-rotated record, which is what the rotation slice counts as "already rotated"; a record that opens under *neither* key raises `CryptoError` rather than being reported as done, so a corrupt row stops a rotation instead of being silently skipped.
- **`nacl.exceptions.CryptoError` propagates**; no wrapper exception. Nothing outside `rewrap` needs to catch it — a vault row that will not open is unrecoverable, not a branch — and a wrapper would only add a layer to read through.
- **One `MasterKeyError` for all three boot failures** (missing, not base64, wrong length), each with its own message naming the variable. The operator has one variable to fix; the exception type is not the place to distinguish how it is wrong. The value is stripped before decoding, because a key delivered as a compose secret arrives with the file's trailing newline.
- **The gate is a FastAPI lifespan**, not an import-time check: `python -m step_by_step_api.export` (which `pnpm build` runs for the OpenAPI schema) imports the app and must not need a key, while uvicorn runs the lifespan and exits when it raises. `TestClient(app)` outside a `with` block runs no lifespan, so the existing tests are unaffected.
- **`STEPBYSTEP_MASTER_KEY` sits on the `api` service alone in compose.yaml**, deliberately outside the `x-stack-environment` anchor the Workers share — ADR 0004 enforced by the file's structure. It carries a fixed dev default on the same terms as Garage's credentials above it, so a cold `docker compose up` still needs no `.env`.

Facts for a reviewer:

- PyNaCl is the new production dependency, on `apps/api` only (never `packages/core`, or the Worker image would carry it). ADR 0003 states the reason; the standard library has no AEAD.
- Verified in the built images, not just in tests: the api container boots and serves `/api/health` with the compose-supplied key, and refuses to start with `MasterKeyError` on a bad one ("Application startup failed. Exiting."); the worker container has neither `nacl` nor `step_by_step_api` installed.
- Tests: `apps/api/tests/test_envelope.py` (the module directly, the seam the spec's Testing Decisions names) and `apps/api/tests/test_boot.py` (the gate through the app's real startup). Both fast tier — nothing here needs a service.
- `docs/ARCHITECTURE.md` gained a "The vault's encryption" seam section.
- `pnpm run ci` green; the integration tier green against the running stack; `openapi.json` unchanged, as a lifespan adds no routes.

Left for later slices, as scoped: the `rotate-master-key` CLI (the primitive is here, the command lands with the rotation slice), and every table that will call `seal`.
