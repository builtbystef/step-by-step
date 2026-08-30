# 0003 — Environment master key with application-level envelope encryption

## Context

Secrets and Auth State are bearer credentials stored in PostgreSQL. A self-hosted Compose deployment cannot depend on a cloud key-management service.

## Decision

The API encrypts each Secret and Auth State record with its own data key. It wraps each data key with one 32-byte master key supplied through `STEPBYSTEP_MASTER_KEY`. PostgreSQL never stores plaintext credentials.

Losing the master key makes the encrypted values unrecoverable.

## Reason

An environment key works in every supported deployment. Per-record data keys also allow master-key rotation and leave room for a future key-management service.
