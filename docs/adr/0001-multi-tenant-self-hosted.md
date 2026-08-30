# 0001 — Multi-tenant data model in a self-hosted tool

Status: superseded by ADR 0005.

## Context

A self-hosted instance may serve many people. Adding ownership to every table later would be costly.

## Decision

The first design made each user a tenant and made every Workflow, Run, Batch, and secret Variable belong to one user. Teams and roles were left for later.

ADR 0005 replaced user tenancy with Organization tenancy.
