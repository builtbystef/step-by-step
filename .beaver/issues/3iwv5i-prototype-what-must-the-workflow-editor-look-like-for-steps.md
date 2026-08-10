---
id: 3iwv5i
title: 'Prototype: what must the workflow editor look like for steps, variables, and publishing?'
state: todo
priority: high
labels:
    - roadmap:idnzwf
    - session:prototype
depends_on:
    - ds8zyn
parent: idnzwf
created: 2026-08-08T08:57:41Z
updated: 2026-08-08T08:57:41Z
---

Live prototype session (prototype skill). The data model is settled (ds8zyn): draft + published Versions, step envelope (label, optional, timeout override, disabled), ranked selector candidates per targeting step, {{name}} variable interpolation, extract steps with output names and scalar/list modes. Answer with disposable UI:

- How does the step list read and edit: per-type payload forms, reorder, disable, labels?
- How are a step's ranked selector candidates shown and repaired without overwhelming a non-technical user?
- How are Variables declared and referenced ({{name}} in values), and how does the editor surface where each is used?
- What does the draft → test run → publish flow look like in the editor?

Inputs: ds8zyn's note, docs/GLOSSARY.md, f10wq3's selector research. The result feeds the recording+editing+storage spec.
