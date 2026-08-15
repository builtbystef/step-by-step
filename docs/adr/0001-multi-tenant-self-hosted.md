# 0001 — Multi-tenant data model in a self-hosted tool

Status: superseded by ADR 0005 — the tenant is now the Organization, not the user.

Context: Step by Step ships as self-hosted open source, an org may host one instance for many people, and a hosted paid version is a possible future. Decision: the data model is multi-tenant from day one — every Workflow, Run, Batch, and secret Variable belongs to exactly one user — while v1 has no teams, sharing, or org roles. Reason: retrofitting per-user ownership onto every table later is painful, while deferring teams until the need appears costs nothing now.
