# PROTOTYPE — disposable. One-shot Playwright replay of a proto-recording.json.
# Ordered first-match-wins fallback over each step's ranked candidates (f10wq3):
# resolve candidates by rank, first that matches exactly one element acts.
# Prints which candidate rank/kind won every step.
import json
import sys
import tempfile

from playwright.sync_api import sync_playwright

TIMEOUT_MS = 10_000

# Chromium AX role values that differ from the ARIA role Playwright expects.
ROLE_MAP = {"textField": "textbox", "popUpButton": "combobox", "comboBoxSelect": "combobox"}


def build_locator(page, cand):
    k = cand["kind"]
    if k == "role":
        return page.get_by_role(ROLE_MAP.get(cand["role"], cand["role"]), name=cand["name"], exact=True)
    if k == "testid":
        return page.locator(f'[{cand["attr"]}="{cand["value"]}"]')
    if k == "placeholder":
        return page.get_by_placeholder(cand["value"], exact=True)
    if k == "label":
        return page.get_by_label(cand["value"], exact=True)
    if k == "alt":
        return page.get_by_alt_text(cand["value"], exact=True)
    if k == "text":
        return page.get_by_text(cand["value"], exact=True)
    if k == "title":
        return page.get_by_title(cand["value"], exact=True)
    if k == "css":
        return page.locator(cand["value"])
    raise ValueError(f"unknown candidate kind {k}")


def resolve(page, step):
    """Ordered fallback: first candidate resolving to exactly one element wins."""
    attempts = []
    for rank, cand in enumerate(step["selectors"]):
        label = f'{cand["kind"]}:{cand.get("value") or cand.get("name")}'
        try:
            loc = build_locator(page, cand)
            n = loc.count()
        except Exception as e:
            attempts.append(f"  rank {rank} {label} -> error {e}")
            continue
        if n == 1:
            return loc, rank, cand, attempts
        attempts.append(f"  rank {rank} {label} -> {n} matches")
    return None, None, None, attempts


def main(path):
    recording = json.load(open(path))
    steps = recording["steps"]
    results = []
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        page.set_default_timeout(TIMEOUT_MS)
        for i, step in enumerate(steps):
            t = step["type"]
            desc = f"[{i}] {t}"
            try:
                if t == "navigate":
                    page.goto(step["url"])
                    results.append((desc, "goto", step["url"], "ok"))
                    continue
                if t == "download" and "selectors" not in step:
                    results.append((desc, "-", step.get("url"), "standalone download event, nothing to replay"))
                    continue

                loc, rank, cand, attempts = resolve(page, step)
                if loc is None:
                    results.append((desc, "NONE", None, "NO CANDIDATE RESOLVED:\n" + "\n".join(attempts)))
                    continue
                won = f'rank {rank} ({cand["kind"]}: {cand.get("value") or cand.get("name")})'

                if t == "click":
                    if step.get("download"):
                        with page.expect_download() as dl:
                            loc.click()
                        f = tempfile.mktemp(prefix="proto-dl-")
                        dl.value.save_as(f)
                        results.append((desc, won, None, f"ok, downloaded {dl.value.suggested_filename} -> {f}"))
                    else:
                        loc.click()
                        if step.get("assertedNavigation"):
                            page.wait_for_url(step["assertedNavigation"])
                        results.append((desc, won, None, "ok"))
                elif t == "fill":
                    loc.fill(step["value"])
                    results.append((desc, won, None, f'ok, filled {"***" if step.get("isPassword") else step["value"]!r}'))
                elif t == "select":
                    loc.select_option(step["value"])
                    results.append((desc, won, None, f'ok, selected {step["value"]!r}'))
                elif t == "extract":
                    text = " ".join(loc.text_content().split())
                    match = text == step["capturedText"]
                    results.append((desc, won, None, f"ok, extracted {text!r} (matches recording: {match})"))
                else:
                    results.append((desc, won, None, f"unknown step type {t}, skipped"))
            except Exception as e:
                results.append((desc, "-", None, f"FAILED: {e}"))
        browser.close()

    print("\n=== replay report ===")
    failures = 0
    for desc, won, extra, outcome in results:
        line = f"{desc:<14} winner: {won:<50} {outcome}"
        if extra:
            line += f" {extra}"
        print(line)
        if "FAILED" in outcome or "NO CANDIDATE" in outcome:
            failures += 1
    print(f"\n{len(results)} steps, {failures} failures")
    ax = [t.get("totalMs") for t in recording.get("axTimings", []) if t.get("ok")]
    if ax:
        print(f"record-time CDP role/name query cost: n={len(ax)} avg={sum(ax)/len(ax):.0f}ms max={max(ax)}ms")


if __name__ == "__main__":
    main(sys.argv[1])
