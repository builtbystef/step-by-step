# 0004 — Workers never hold the master key

## Context

Workers write execution results directly to PostgreSQL and run browser content that cannot be trusted. A Worker with the master key could decrypt every Organization's vault.

## Decision

Only the API receives `STEPBYSTEP_MASTER_KEY`. The encryption module is not included in the Worker image. A Worker asks an authenticated internal API endpoint for the resolved plaintext needed by its assigned Run.

## Reason

This limits a Worker to credentials for the Run it is executing instead of giving it access to every stored Secret and Auth State record.
