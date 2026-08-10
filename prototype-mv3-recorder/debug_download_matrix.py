# PROTOTYPE — disposable. Why do clicks on /download vanish in the harness?
# Matrix: (A) no extension, (B) extension idle, (C) extension recording (debugger attached).
import shutil
from pathlib import Path

from playwright.sync_api import sync_playwright

EXT = str(Path(__file__).resolve().parent / "extension")
SCRATCH = "/tmp/claude-1000/-home-stefan-Code-personal-step-by-step/d88b55bf-8f55-4c79-be40-824e6ff2e6ea/scratchpad"


def probe(page):
    page.evaluate(
        "window.__clicks = 0; window.addEventListener('click', e => { window.__clicks++; }, true)"
    )
    page.click("h3")
    page.mouse.click(300, 200)
    page.wait_for_timeout(300)
    return page.evaluate("window.__clicks")


def run(label, use_ext, record):
    profile = f"{SCRATCH}/matrix-{label}"
    shutil.rmtree(profile, ignore_errors=True)
    with sync_playwright() as p:
        args = [f"--disable-extensions-except={EXT}", f"--load-extension={EXT}"] if use_ext else []
        ctx = p.chromium.launch_persistent_context(profile, headless=True, channel="chromium", args=args)
        page = ctx.new_page()
        page.goto("https://the-internet.herokuapp.com/download")
        if record:
            sw = ctx.service_workers[0] if ctx.service_workers else ctx.wait_for_event("serviceworker")
            sw.evaluate(
                """async () => {
                    const tabs = await chrome.tabs.query({});
                    const tab = tabs.find(t => (t.url||'').includes('the-internet'));
                    await start(tab.id);
                }"""
            )
            page.wait_for_timeout(300)
        clicks = probe(page)
        print(f"{label}: click events seen in page = {clicks}")
        ctx.close()


run("A-no-extension", False, False)
run("B-extension-idle", True, False)
run("C-extension-recording", True, True)
