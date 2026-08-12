---
id: 7mfxzj
title: 'Prototype: the shell, the list screens, and the visual language they establish'
state: done
assignee: claude
priority: high
labels:
    - roadmap:idnzwf
    - session:prototype
depends_on:
    - dm4cff
parent: idnzwf
created: 2026-08-12T03:52:07Z
updated: 2026-08-12T04:50:20Z
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

## Notes

**claude** — 2026-08-12T04:50:04Z

ANSWER — the app shell is Shell A, and the visual language is named. Verdict in the user's words: "I want to go with Shell A, ban over content", "This all looks great", "Everything looks great", then "Done".

Prototype branch: prototype/app-shell, file PROTOTYPE-app-shell.html. One self-contained page, no build step, no server. Its harness switches shell variant, screen, row count (0/3/40), attention count (0/1/3), extension state, and frame width (1440-880) independently, so any combination is reachable.

THE SHELL — variant A: the attention band spans the content column, directly under the top of the main area, above the page title. Rejected: B (the band inside the sidebar) and C (a pill in a persistent top bar). B can name only one Run and costs sidebar height; C is the quietest and easiest to miss, which is wrong for a signal whose whole reason to exist is a 30-minute deadline that fails the Run when it passes. The sidebar is labelled down to 1024px and collapses to a 60px icon rail below that, keeping the count badge visible.

THE VISUAL LANGUAGE — four foundations and eleven primitives, each rendered on the LANGUAGE tab with a provenance line saying which earlier prototype it came from.

Foundations. (1) Surfaces and ink: --bg #f5f6f8, --panel #ffffff, --ink #1a2130, --mut #68738a, --line #e3e7ee. (2) The semantic ramp, one hue one meaning: --accent #2f6fed the machine is acting or this is informational; --wait #b97a08 a human is needed or was; --human #7c3aed a secret or human-supplied value; --ok #178a50; --bad #c92f34. (3) Type scale, six sizes: 11 micro, 12 small, 13 table/callout, 14 body (system-ui, 1.45), 16 title, 20 page. Monospace only for machine strings — selectors, cron, ids. (4) Spacing 4/6/8/12/16/24; radius 6 controls, 8 callouts, 10 cards, 999 pills.

Primitives: status chip (.chip, lifecycle state, pill, live states carry a dot, running pulses); attribute badge (.badge, rectangular, a property never a state); callout (.note, tone x size, inline or page-width banner); attention band; count badge (grey a total, blue in flight, amber waiting on you); connection pill; locked cell (vault-sourced grid cell, purple, names its entry); hatched occurrence (45deg 3px hatch = nothing happens here; amber = prevented, grey = never due); expand-in-place row; sticky action footer; empty state (one bold sentence naming what is absent, one grey sentence saying what fills it, one button going there).

FOUR ARBITRATIONS SETTLED — each was a real disagreement between shipped prototypes, all four resolved as proposed and approved by the user.
1. .badge carried two taxonomies: selector health in workflow-editor (optional/disabled/fragile), step outcomes in live-run-view (drift/human/bad/skip/ok). Badge is now ATTRIBUTES ONLY; every lifecycle state moves to .chip. live-run-view's .badge.ok and .badge.skip were chips wearing the wrong shape.
2. .chip.skipped was grey in batch-creation and live-run-view, amber in schedule-creation. Grey wins. Amber is reserved for "a human is needed", and no skip needs one — a Batch row skipped for a missing value and an Occurrence skipped for overlap both simply did not run, and both stay re-runnable.
3. Three callout families for one idea (.note.* in batch and schedule, .banner.* and .driftbox in live-run-view). One component, tone x size. .driftbox becomes .note.warn; .banner.gray becomes .note.info.
4. --drift #a8600b sat 10 degrees of hue from --wait #b97a08 and was indistinguishable in a badge. DELETED. Selector drift IS "a human should look at this", so it is amber, distinguished by its words and icon, not by a hue nobody can name. Arbitration 3 removed its last user.

Also: workflow-editor is the palette outlier — it names the same intents --text/--muted/--border over a warmer #f6f7f9 and uses accent #3b5bdb. The four-prototype set wins; that prototype gets re-skinned when d8ux2s is implemented, a find-and-replace with no layout change. live-run-view's --auto is renamed --accent, since the same blue is the app's interactive accent everywhere else.

STACK FACT, from the user this session: the app will be built with shadcn/ui over Tailwind. The node had listed component-library choice as out of bounds (belonging with ymz3md); the user made the call anyway, so it is recorded here rather than re-litigated, and noted on ymz3md. It splits the language three ways. FREE from shadcn: status chip and attribute badge -> Badge with two variant sets; callout -> Alert; data table -> Table; expand-in-place -> Collapsible in a table row; empty state -> Card; the shell -> Sidebar, which already ships the icon-collapse this prototype hand-rolls; count badge -> SidebarMenuBadge; every dialog, select, input, dropdown. THEME: --bg/--panel/--ink/--mut/--line/--accent map onto shadcn's --background/--card/--foreground/--muted-foreground/--border/--primary, and the spacing and radius scales are Tailwind defaults (1/1.5/2/3/4/6). BUILT HERE, because shadcn has nothing for them: the attention band's polling, live countdown and every-screen placement; the locked cell; the hatched occurrence; the connection pill's three states with one deliberately-merged failure case; the sticky action footer; the one reused unpublished-Version sentence. THE IMPORTANT LINE: shadcn ships only --destructive, so THE SEMANTIC RAMP HAS NO LIBRARY EQUIVALENT — --wait, --human and --ok are additions to the theme, and the one-hue-one-meaning rule is this node's to enforce, not the library's.

COPY CHANGE, user-requested: the closed-signup screen (what /signup renders once the instance has its first account, unless open signup is on) reads "Sign-up is unavailable / This instance does not offer self-serve sign-up. Ask an Instance Admin to create an account for you — they can set a temporary password, and you will choose your own the first time you sign in." A plain page with that sentence, never a 404.

SCREENS DRAWN, confirmed against dm4cff: Workflows list at 0/3/40 rows (search box and sort control appear only at scale; a never-published Workflow reads "not published yet", has no Run history and no Schedule, and its Run action is disabled behind the one shared sentence); Runs history as one component with status and trigger filters, rows navigating rather than expanding; the all-Schedules table with rows expanding in place; Settings with its sections and the Admin group rendered only for an Instance Admin; the four auth screens outside the shell; and the first-run panel of two numbered steps, which is what the Workflows screen IS at zero Workflows.

NO GLOSSARY ADDITIONS — this node names UI primitives, not domain concepts. NO ADR: the stack fact belongs to ymz3md, and every arbitration here is cheap to reverse.
