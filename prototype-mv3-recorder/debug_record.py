# PROTOTYPE — disposable. Local record-loop harness: loads the extension into a
# Playwright-driven Chromium, performs the same flow we ran live, then dumps the
# recording JSON from chrome.storage for inspection/replay.
import json
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

EXT = str(Path(__file__).resolve().parent / "extension")
PROFILE = "/tmp/claude-1000/-home-stefan-Code-personal-step-by-step/d88b55bf-8f55-4c79-be40-824e6ff2e6ea/scratchpad/proto-profile"
OUT = Path(__file__).resolve().parent / "harness-recording.json"


def main():
    import shutil

    shutil.rmtree(PROFILE, ignore_errors=True)
    with sync_playwright() as p:
        ctx = p.chromium.launch_persistent_context(
            PROFILE,
            headless=True,
            channel="chromium",
            args=[f"--disable-extensions-except={EXT}", f"--load-extension={EXT}"],
        )
        sw = ctx.service_workers[0] if ctx.service_workers else ctx.wait_for_event("serviceworker")

        page = ctx.new_page()
        page.on("console", lambda m: ("protorec" in m.text or m.type == "error") and print("PAGE:", m.type, m.text))
        page.on("pageerror", lambda e: print("PAGEERROR:", e))
        page.goto("https://the-internet.herokuapp.com/login")

        tab_id = sw.evaluate(
            """async () => {
                const tabs = await chrome.tabs.query({});
                const tab = tabs.find(t => (t.url||'').includes('the-internet'));
                await start(tab.id);
                return tab.id;
            }"""
        )
        print("recording started on tab", tab_id)

        page.click("#username")
        page.keyboard.type("tomsmith")
        page.click("#password")
        page.keyboard.type("SuperSecretPassword!")
        page.click("button[type=submit]")
        page.wait_for_url("**/secure")

        page.click("#proto-extract-toggle")
        page.click("#flash")

        page.goto("https://the-internet.herokuapp.com/dropdown")
        # No click on the select: the native popup it opens is a browser-level
        # window that CDP input cannot close, and it swallows all later clicks.
        page.select_option("#dropdown", "2")

        page.goto("https://the-internet.herokuapp.com/download")
        print(
            "content script alive on /download:",
            page.evaluate("!!document.getElementById('proto-extract-toggle')"),
        )
        try:
            with page.expect_download(timeout=8000) as dl:
                page.click("text=some-file.txt")
            print("downloaded:", dl.value.suggested_filename)
        except Exception as e:
            print("download step did not complete in harness:", e)
        print("post-click url:", page.url)
        dl_state = sw.evaluate("chrome.downloads.search({}).then(d => d.map(x => [x.url, x.state]))")
        print("chrome.downloads sees:", dl_state)

        # Probe: do clicks reach the page's main world at all?
        page.evaluate(
            "window.addEventListener('click', e => console.log('[protorec-MAIN] click', e.target.tagName), true)"
        )
        page.click("h3")
        page.click("text=some-file.txt")
        page.wait_for_timeout(1500)
        dl_state = sw.evaluate("chrome.downloads.search({}).then(d => d.map(x => [x.url, x.state]))")
        print("chrome.downloads after bare click:", dl_state)

        page.wait_for_timeout(1000)  # let trailing prefetches/persists settle
        recording = sw.evaluate(
            """async () => {
                await stop();
                const { recording } = await chrome.storage.local.get('recording');
                return recording;
            }"""
        )
        ctx.close()

    OUT.write_text(json.dumps(recording, indent=2))
    print("\nnotes:", recording["notes"])
    for i, s in enumerate(recording["steps"]):
        sels = [
            (c["kind"], c.get("value") or (c.get("role"), c.get("name")), c["verified"])
            for c in s.get("selectors", [])
        ]
        extra = {
            k: s[k]
            for k in ("value", "optionLabel", "capturedText", "assertedNavigation", "download", "transition", "url")
            if s.get(k) is not None and (k != "url" or s["type"] == "navigate")
        }
        print(f"[{i}] {s['type']} {sels if sels else ''} {extra}")
    ax = [t for t in recording["axTimings"] if t.get("ok")]
    bad = [t for t in recording["axTimings"] if not t.get("ok")]
    if ax:
        ms = [t["totalMs"] for t in ax]
        print(f"\nax ok={len(ax)} avg={sum(ms)/len(ms):.0f}ms max={max(ms)}ms failed={len(bad)}")
    for t in bad:
        print("  ax failed:", t.get("error"))
    print("saved to", OUT)


if __name__ == "__main__":
    main()
