from urllib.parse import urlparse

from playwright.sync_api import Error as PlaywrightError
from playwright.sync_api import Page

CHALLENGE_IFRAME_HOSTS = (
    "recaptcha.net",
    "hcaptcha.com",
    "challenges.cloudflare.com",
)

CHALLENGE_CONTAINERS = (
    ".g-recaptcha",
    ".h-captcha",
    ".cf-turnstile",
    "#challenge-form",
    "#challenge-stage",
    "#challenge-running",
    "#cf-challenge-running",
)

CONTAINER_SELECTOR = ", ".join(CHALLENGE_CONTAINERS)


def host_is_challenge(src: str) -> bool:
    host = (urlparse(src).hostname or "").lower()
    return any(
        host == suffix or host.endswith(f".{suffix}")
        for suffix in CHALLENGE_IFRAME_HOSTS
    )


def page_shows_challenge(page: Page) -> bool:
    try:
        frames = page.frames
    except PlaywrightError:
        return False
    for frame in frames:
        try:
            if frame.locator(CONTAINER_SELECTOR).count() > 0:
                return True
            srcs = frame.locator("iframe").evaluate_all("els => els.map(el => el.src)")
        except PlaywrightError:
            continue
        if any(isinstance(src, str) and host_is_challenge(src) for src in srcs):
            return True
    return False
