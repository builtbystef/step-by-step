---
id: 3iwv5i
title: 'Prototype: what must the workflow editor look like for steps, variables, and publishing?'
state: done
assignee: claude
priority: high
labels:
    - roadmap:idnzwf
    - session:prototype
depends_on:
    - ds8zyn
parent: idnzwf
created: 2026-08-08T08:57:41Z
updated: 2026-08-10T05:12:47Z
---

Live prototype session (prototype skill). The data model is settled (ds8zyn): draft + published Versions, step envelope (label, optional, timeout override, disabled), ranked selector candidates per targeting step, {{name}} variable interpolation, extract steps with output names and scalar/list modes. Answer with disposable UI:

- How does the step list read and edit: per-type payload forms, reorder, disable, labels?
- How are a step's ranked selector candidates shown and repaired without overwhelming a non-technical user?
- How are Variables declared and referenced ({{name}} in values), and how does the editor surface where each is used?
- What does the draft → test run → publish flow look like in the editor?

Inputs: ds8zyn's note, docs/GLOSSARY.md, f10wq3's selector research. The result feeds the recording+editing+storage spec.

## Notes

**claude** — 2026-08-10T05:12:47Z

VERDICT (user, live prototype session 2026-08-10): "go with a hybrid of A and C" — the editor is a vertical inline card list (variant A's structure) whose card summary line is the narrative sentence (variant C's reading): bold editable label on top, beneath it the step as a sentence with variable pills and target tokens ("Type {{password}} into Password field"). Click a card to expand its full form in place; hover tools for reorder/disable/delete; badge column right (optional / off / timeout override / fragile target). Pure master-detail (B) and pure narrative (C) were rejected as the primary layout: cards scale to long recorded workflows and carry the envelope metadata; sentences win comprehension — the hybrid keeps both.

Validated as prototyped, no objections raised:
- Selector candidates: collapsed panel per targeting step, "How this step finds '<element>'" with a plain-language health badge (green "N ways to find it - verified when recorded" / amber "fragile - only position-based selectors", surfacing also as a card badge). Expanded: ranked candidate rows (kind chip, value, unique check), move-to-top / remove, "Pick element again..." (recorder round-trip) and "Add selector by hand" as the repair paths.
- Variables: declared in a drawer (name, secret flag, delete); each row shows "used by N steps" which highlights and scrolls to usages; deleting a used Variable is refused; unused is flagged amber. Values referenced as {{name}} pills inside Type values and Navigate URLs, inserted via a dropdown; secret pills styled distinctly and masked in the test-run form.
- Draft -> test run -> publish: header carries the workflow name, a Draft chip ("unpublished changes" amber / "in sync with vN" green), a version dropdown (Draft + immutable vN history, past versions open read-only with restore-to-Draft), Test run (modal prompts per-run Variable values, secrets masked; Run is flagged a test run, no Version minted), Publish vN+1 (modal with step-level diff summary vs the last Version, then the chip flips to in-sync).

Prototype code: branch prototype/workflow-editor (single file PROTOTYPE-workflow-editor.html, opens directly in a browser; variant A is the chosen hybrid, B and C kept for comparison). Feeds spec node u8q8p3.
