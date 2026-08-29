# Coding standards

The conventions that this project holds, beyond what linters and formatters enforce. Reviews check diffs against this file. Keep each rule current, or delete it.

## Dependencies

- Prefer what the project already has: an installed library, or the standard library, before a new dependency.
- A new production dependency needs a stated reason, in the issue that adds it. A new dependency is never the default answer to a small problem.

## The frontend's visual language

Defined by spec `pc0t8s` and built in `8cjj8g`. Three rules a review checks against a diff:

- **No raw hex outside `apps/web/app/globals.css`.** That file defines the surfaces and the semantic ramp; every other file reaches a colour through a token, so one hue keeps one meaning.
- **No lifecycle state rendered except through `StatusChip`.** A state's wording comes from `apps/web/lib/labels.ts` and nowhere else, and `AttributeBadge` carries properties only — never a state a Run, an Occurrence, or a Batch row can be in.
- **One file per shared list.** Run rows and Schedule rows each have one component; the global screen and the Workflow tab are that component with an optional `workflowId`. A second file that renders Run rows or Schedule rows breaks the rule.

The first two are also asserted by `apps/web/visual-language.test.ts`, which scans the frontend's own source.

Beyond them: an idea has one primitive in `apps/web/components/primitives/`, and a sentence that two screens must say identically lives in `apps/web/lib/copy.ts`. `apps/web/components/ui/` is shadcn's, generated and not hand-edited.
