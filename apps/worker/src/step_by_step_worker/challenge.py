"""The built-in signals that a page is presenting an auth challenge.

The provider hosts and container selectors are a constant. They are not
user-configurable and not extensible at runtime.
"""

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
    """Whether an iframe src points at a known challenge provider."""
    host = (urlparse(src).hostname or "").lower()
    return any(
        host == suffix or host.endswith(f".{suffix}")
        for suffix in CHALLENGE_IFRAME_HOSTS
    )


def page_shows_challenge(page: Page) -> bool:
    """Whether the page currently carries a known challenge signal."""
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
