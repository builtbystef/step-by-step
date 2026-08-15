---
id: 8cjj8g
title: 'The visual language: theme tokens, type scale, and the eleven primitives'
state: todo
priority: high
parent: pc0t8s
created: 2026-08-14T05:54:19Z
updated: 2026-08-14T05:54:19Z
---

## What to build

The frontend foundation every later screen inherits, so implementers meet a vocabulary instead of inventing one. Set up Tailwind CSS, shadcn/ui, and TanStack Query (the stack facts recorded on ymz3md). Define the surfaces, the five-hue semantic ramp, and the six-size type scale as theme tokens mapped onto the library's own token names. Build the eleven named primitives, one file each, with a single labels module as the only source of state wording and a shared-copy module for sentences that must be identical across screens. The spec (pc0t8s) is the language's durable record; branch `prototype/app-shell`'s LANGUAGE tab renders every primitive for reference. The four arbitrations are settled: badges carry attributes only, `skipped` is grey, there is one callout family, and no drift hue exists.

## Acceptance criteria

- [ ] Tailwind, shadcn/ui-generated components, and TanStack Query are installed and pass the four check commands; mutations never retry (a retried Run-start acts twice on a real website), and query retry/staleTime are chosen per key, not inherited.
- [ ] The theme defines the surfaces (bg `#f5f6f8`, panel `#ffffff`, ink `#1a2130`, muted `#68738a`, line `#e3e7ee`) and the semantic ramp — accent `#2f6fed`/`#e8effd` = the machine is acting; wait `#b97a08`/`#fdf3e0` = a human is needed or was; human `#7c3aed`/`#f1eafd` = a secret or human-supplied value; ok `#178a50`/`#e2f5ea` = succeeded; bad `#c92f34`/`#fbe9e9` = failed — mapped onto the library's token names. No drift token exists.
- [ ] The type scale is exactly six sizes (11 micro, 12 small, 13 half-step, 14 body, 16 title, 20/700 page); spacing and radius use Tailwind defaults; monospace appears only on machine strings (selectors, cron, ids, countdowns).
- [ ] All eleven primitives exist, each the only place its idea is rendered: StatusChip (pill, live states carry a leading dot, running pulses, grey for queued/cancelled/cancelling/skipped/missed/paused, accent running, wait waiting_for_human, ok succeeded, bad failed), AttributeBadge (rectangular, properties never lifecycle), Callout (tone × size, one family), AttentionBand, CountBadge (grey total, blue in flight, amber waiting-on-you, hidden at zero), ConnectionPill (three states), LockedCell (purple, lock, Secret name, never the value), HatchedOccurrence (amber hatch prevented, grey never due), ExpandableRow, StickyActionFooter, EmptyState (bold absence sentence, grey what-fills-it sentence, one button — always three parts). Primitives that later slices wire (AttentionBand, CountBadge, ConnectionPill) are pure over props here.
- [ ] One labels module is the single source of every lifecycle state's wording — `waiting_for_human` reads "needs you" everywhere — and one shared-copy module holds the cross-screen sentences, starting with "Publish a Version before this Workflow can run."
- [ ] The two reviewable rules hold across the diff: no raw hex outside the token definitions, and no lifecycle state rendered except through StatusChip.
- [ ] No dark mode, no second palette, and no live primitive-gallery route.
