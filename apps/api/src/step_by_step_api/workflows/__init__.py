"""Workflows: the document store the recorder writes and the editor edits.

A Workflow belongs to exactly one Organization (ADR 0005) and carries the two
timeouts a Run reads. Its Steps and Variables do not live in tables: the
single mutable Draft — and, later, each published Version — holds one
self-contained JSONB document, so a per-type payload change is a code change
rather than a migration.
"""
