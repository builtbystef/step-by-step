---
id: pjxuqx
title: 'Prototype: how does a user create and read a Schedule?'
state: todo
priority: medium
labels:
    - roadmap:idnzwf
    - session:prototype
depends_on:
    - kvz5sv
parent: idnzwf
created: 2026-08-12T01:03:52Z
updated: 2026-08-12T01:03:52Z
---

Live prototype session (prototype skill). The scheduling *engine* is settled — spec 9gea5p fixes cron plus an IANA timezone, overlap means the occurrence is skipped, missed occurrences are never caught up, and a Schedule executes the Workflow's latest published Version. What no node has answered is the surface. Answer with disposable UI:

- How is a recurrence entered by someone who does not know cron: presets, a builder, a raw expression, or a combination — and how is the result read back in words?
- What does the next-run preview show (the next few occurrences, in which timezone, against what "now")?
- How is the timezone chosen, and what does a user see when theirs differs from the instance's?
- How does a Schedule read at rest: last fired, next due, enabled/disabled, and the runs it produced?
- How does the skip-on-overlap rule surface after it fires, so that a missing run is never a mystery?
- Where do Variable values for a scheduled Run come from, given that nobody is present to type them?

The last question may not be answerable as UI alone — if it turns out to be a decision rather than a design, say so in the note and let it become a grill node.

Inputs: the scheduler half of spec 9gea5p, ds8zyn's Variable model, docs/GLOSSARY.md. The result feeds the spec for this area.
