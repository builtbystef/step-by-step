---
id: 7mfxzj
title: 'Prototype: the shell, the list screens, and the visual language they establish'
state: todo
priority: high
labels:
    - roadmap:idnzwf
    - session:prototype
depends_on:
    - dm4cff
parent: idnzwf
created: 2026-08-12T03:52:07Z
updated: 2026-08-12T03:52:07Z
---

Live prototype session (prototype skill). `dm4cff` settles which top-level screens exist and what each answers; this node answers what they look like — and, because it is the first surface every other screen sits inside, what visual language the whole app inherits. Answer with disposable UI:

- **The shell**: navigation, its behavior at laptop width, and where identity, the extension's connection state, and the Instance Admin's entry sit.
- **The Workflows list and the Runs history** as `dm4cff` defined them: row density, what a row shows at a glance, the actions, and how each reads with 0, 3, and 40 items.
- **The empty and first-run states**, which are a real screen here and not a footnote — an instance with no Workflows and no extension installed is the ordinary starting condition of a self-hosted deployment.
- **The visual language**: the type scale, spacing, the status colors, and the small set of primitives the five published specs already assume in prose — status chip, amber callout, red banner, locked column, drift badge, hatched occurrence, expand-in-place row, sticky footer. Name each one, and check it against how the earlier prototypes actually drew it.

The last item is the reason this node exists as much as the first. Five specs describe screens using words like "amber callout" and "status chip" with no shared definition behind them; without one, the first implementation session invents a vocabulary by accident and every later session inherits it.

Inputs: the five published specs, and the earlier prototype branches, which are the evidence for what these primitives already look like — `prototype/workflow-editor` (3iwv5i), `prototype/live-run-view` (apx4rs), `prototype/takeover-ux` (4tjwpw), `prototype/batch-creation` (tf6796), `prototype/schedule-creation` (pjxuqx), `prototype/mv3-recorder` (zm0rfq). Steal from them; they each solved a piece of this in isolation.

Out of bounds: re-deciding any specced surface's layout, and picking a component library or CSS framework — that is a stack decision belonging with `ymz3md` and the Frontier's dev-environment entry. This node settles what the language *is*, not what implements it.

The result, with `dm4cff`, feeds a spec for the app-shell area.
