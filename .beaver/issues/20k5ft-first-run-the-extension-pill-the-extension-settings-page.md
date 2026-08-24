---
id: 20k5ft
title: 'First-run: the extension pill, the extension settings page, and the install panel'
state: done
assignee: agent
priority: medium
depends_on:
    - hat4cf
    - 5rkj33
    - 94xanm
parent: pc0t8s
created: 2026-08-14T05:56:03Z
updated: 2026-08-24T07:12:00Z
---

## What to build

The guided path from a fresh instance to a connected extension, and the surfaces that show its state. The sidebar footer's connection pill gets its three real states from the extension handshake probe; the extension section of Settings becomes its full surface; and the empty Workflows screen becomes a two-step first-run panel, because installation is unpacked and manual. The app cannot distinguish "not installed" from "installed but pointed elsewhere" — those render as one state with one recovery path, and the copy says so plainly.

## Acceptance criteria

- [ ] The page probes for the extension's handshake message carrying its version, treats 1500 ms of silence as not connected, and re-probes on window focus.
- [ ] The pill shows connected with the version (green) when the handshake version meets the unauthenticated version endpoint's minimum; out of date (amber) below it, with recording blocked; not connected (grey) otherwise — and not-installed versus not-pointed-here is deliberately one state.
- [ ] The extension Settings section replaces its placeholder: the download, the unzip → extensions page → Developer mode → Load unpacked sequence, the connect instructions (entering this instance's address in the extension popup), the live connection state, and the current and minimum supported versions.
- [ ] A user with no Workflows sees the Workflows screen as a two-step panel: step 1, install and connect the extension — showing live connection state, staying until connected, then collapsing to a green tick; step 2, create your first workflow — always available, because naming a Workflow needs no extension.
- [ ] With at least one Workflow, the panel is gone and the list renders.
- [ ] The editor's no-Steps empty state offers "Record your first steps", with Start recording replaced by the install-and-connect prompt while the extension is not connected.

## Notes

**agent** — 2026-08-24T07:12:00Z

Completed the first-run extension surfaces. The shell now owns one shared 1500 ms page probe, re-runs it on focus, checks the announced build against the instance minimum, and feeds the three-state ConnectionPill, Settings, first-run panel, and editor. The extension injects the probe bridge only into pages at its connected origin and asks the worker to confirm the connection before announcing, so an old bridge cannot look connected after disconnect. Settings now carries the paired download, unpacked install sequence, merged not-installed/pointed-elsewhere recovery copy, live state, and all three relevant versions. Zero Workflows render the two independent setup steps and collapse extension setup after connection; existing lists are unchanged. A no-Step Draft says 'Record your first steps', offers Start recording only for a supported connection, and otherwise shows install/connect recovery; the recording action itself remains 7vuup5's existing scope. Test seam selected for this AFK slice: the page probe's EventTarget boundary and pure compatibility mapping, plus the existing cross-package protocol-name seam; the parent spec explicitly excludes component/DOM tests. Verified: pnpm check; pnpm test (300 Vitest tests plus 4 core, 10 Worker, and 49 API fast-tier tests).
