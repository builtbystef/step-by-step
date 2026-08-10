# PROTOTYPE — disposable. Bisect which prior step kills clicks on /download.
import shutil
from pathlib import Path

from playwright.sync_api import sync_playwright

EXT = str(Path(__file__).resolve().parent / "extension")
SCRATCH = "/tmp/claude-1000/-home-stefan-Code-personal-step-by-step/d88b55bf-8f55-4c79-be40-824e6ff2e6ea/scratchpad"


def probe(page, where):
    page.evaluate("window.__clicks = 0; window.addEventListener('click', () => window.__clicks++, true)")
    page.click("h3" if page.url.endswith("download") else "body")
    page.wait_for_timeout(200)
    print(f"  clicks fire on {where}:", page.evaluate("window.__clicks"))


def run(label, do_login, do_extract, do_dropdown):
    profile = f"{SCRATCH}/bisect-{label}"
    shutil.rmtree(profile, ignore_errors=True)
    with sync_playwright() as p:
        ctx = p.chromium.launch_persistent_context(
            profile, headless=True, channel="chromium",
            args=[f"--disable-extensions-except={EXT}", f"--load-extension={EXT}"],
        )
        sw = ctx.service_workers[0] if ctx.service_workers else ctx.wait_for_event("serviceworker")
        page = ctx.new_page()
        page.goto("https://the-internet.herokuapp.com/login")
        sw.evaluate(
            """async () => {
                const tabs = await chrome.tabs.query({});
                const tab = tabs.find(t => (t.url||'').includes('the-internet'));
                await start(tab.id);
            }"""
        )
        print(label)
        if do_login:
            page.click("#username")
            page.keyboard.type("tomsmith")
            page.click("#password")
            page.keyboard.type("SuperSecretPassword!")
            page.click("button[type=submit]")
            page.wait_for_url("**/secure")
            if do_extract:
                page.click("#proto-extract-toggle")
                page.click("#flash")
        if do_dropdown:
            page.goto("https://the-internet.herokuapp.com/dropdown")
            page.click("#dropdown")
            page.select_option("#dropdown", "2")
        page.goto("https://the-internet.herokuapp.com/download")
        probe(page, "/download")
        ctx.close()


run("D-login-only", True, False, False)
run("E-login+extract", True, True, False)
run("F-full", True, True, True)


def run_g():
    profile = f"{SCRATCH}/bisect-G"
    shutil.rmtree(profile, ignore_errors=True)
    with sync_playwright() as p:
        ctx = p.chromium.launch_persistent_context(
            profile, headless=True, channel="chromium",
            args=[f"--disable-extensions-except={EXT}", f"--load-extension={EXT}"],
        )
        page = ctx.new_page()
        page.goto("https://the-internet.herokuapp.com/dropdown")
        page.click("#dropdown")
        page.keyboard.press("Escape")
        page.select_option("#dropdown", "2")
        page.goto("https://the-internet.herokuapp.com/download")
        probe(page, "/download after Escape-closed dropdown")
        ctx.close()


run_g()
