---
id: i1osfd
title: Envelope encryption, the master-key boot gate, and ADR 0004
state: todo
priority: high
depends_on:
    - h9gene
parent: 54i6da
created: 2026-08-14T06:14:32Z
updated: 2026-08-14T06:14:32Z
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
