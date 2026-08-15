---
id: 20k5ft
title: 'First-run: the extension pill, the extension settings page, and the install panel'
state: todo
priority: medium
depends_on:
    - hat4cf
    - 5rkj33
    - 94xanm
parent: pc0t8s
created: 2026-08-14T05:56:03Z
updated: 2026-08-14T06:04:25Z
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
