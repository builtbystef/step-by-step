---
id: u8q8p3
title: 'Spec: recording, editing, and storage'
state: todo
priority: high
labels:
    - roadmap:idnzwf
    - session:spec
depends_on:
    - 8iuuh8
    - f10wq3
    - ds8zyn
    - 1zg7o0
    - zm0rfq
    - wljln8
    - 3iwv5i
parent: idnzwf
created: 2026-08-08T08:57:50Z
updated: 2026-08-08T08:57:50Z
---

Write the spec for the recording + editing + storage area (session:spec). The area's nodes: v1 scope (8iuuh8), selector research (f10wq3), workflow data model (ds8zyn), MV3 capture research (1zg7o0), recording-extension prototype (zm0rfq), selector-mismatch replay policy (wljln8), editor UX prototype (3iwv5i).

Read those nodes' notes and linked artifacts (this area's only). Interview to close remaining gaps (grill-me), confirm with the user, then invoke the create-specification skill. Publish the spec issue with a blocking edge back to each node it covers.

The spec must carry the save-time validation rule from ds8zyn: reject any step array with duplicate step ids; mint fresh ids when duplicating a workflow.
