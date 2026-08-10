# PROTOTYPE — disposable. Do not ship anything in this directory.

Feasibility prototype for roadmap node `zm0rfq`: can an MV3 extension record a real
workflow into semantic steps with ranked, record-time-verified selectors, and do
those steps replay in Playwright?

## Parts

- `extension/` — unpacked MV3 extension. Records clicks, fills, selects, extracts
  (toggle the floating EXTRACT button on the page), navigations, and downloads on
  `the-internet.herokuapp.com`. Attaches `chrome.debugger` to the recorded tab to
  compute ARIA role + accessible name per event via CDP, and times those queries.
- `replay.py` — reads the recorded JSON, maps each step's ranked selector candidates
  to Playwright locators with ordered first-match-wins fallback, replays once, and
  prints which candidate rank won each step.

## Record

1. `chrome://extensions` → Developer mode → Load unpacked → select `extension/`.
2. Open https://the-internet.herokuapp.com/login in a tab.
3. Click the extension icon → **Start recording** (the debugger infobar appears —
   that is one of the things this prototype observes).
4. Perform the flow. Toggle the floating EXTRACT button before clicking an element
   whose text you want captured as an extract step.
5. Extension icon → **Stop** → **Download JSON** (lands in `~/Downloads/proto-recording.json`).

## Replay

```
python3 -m venv .venv && .venv/bin/pip install playwright && .venv/bin/playwright install chromium
.venv/bin/python replay.py ~/Downloads/proto-recording.json
```

## Automated record loop (no human)

`debug_record.py` loads the extension into a Playwright-driven headless Chromium,
performs the whole flow, dumps `harness-recording.json`, and prints step + timing
diagnostics. Known quirks of that environment (not extension bugs): clicking a
native `<select>` opens a browser-level popup CDP input can't close, which then
swallows all later clicks (use `select_option` without a preceding click); and
Playwright never observes downloads while the extension's debugger is attached,
so the download step only records in a real Chrome session.
`debug_download_matrix.py` / `debug_download_bisect.py` are the experiments that
established this.
