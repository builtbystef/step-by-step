"""Fetch, inject, and write back a Run's already-resolved credentials.

Workers never hold the master key and never learn that Personal Overrides
exist. This module speaks the internal HTTP contract and the browser APIs
that load and capture Auth State.
"""

from __future__ import annotations

import ctypes
import ctypes.util
import ipaddress
import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from functools import cache
from os import environ
from typing import Any, Protocol, cast
from urllib.error import HTTPError
from urllib.parse import urlparse
from urllib.request import Request, urlopen
from uuid import UUID

from playwright.sync_api import BrowserContext, Page

from step_by_step_worker.heartbeat import API_URL_VARIABLE, INTERNAL_TOKEN_VARIABLE

SESSION_COOKIE_EXPIRES = -1


class MissingSecret(Exception):
    """The credentials fetch refused this Run because a bound Secret is gone."""

    def __init__(self, variable_names: Sequence[str]) -> None:
        self.variable_names = list(variable_names)
        names = ", ".join(self.variable_names) or "a secret Variable"
        super().__init__(f"missing Secret for {names}")


@dataclass(frozen=True, slots=True)
class CredentialSet:
    """The plaintext the backend already resolved for this Run."""

    secrets: Mapping[str, str]
    auth_states: Sequence[Mapping[str, Any]]


class Credentials(Protocol):
    """The Worker-facing credential boundary for one claimed Run."""

    def fetch(self) -> CredentialSet: ...

    def consents(self) -> Sequence[str]: ...

    def write_back(
        self,
        states: Sequence[Mapping[str, Any]],
        new_candidates: Sequence[str],
    ) -> None: ...


def site_identity(hostname: str) -> str:
    """The Auth State key for a host: eTLD+1, or the host when that has no meaning."""
    host = hostname.lstrip(".").rstrip(".").lower()
    if not host:
        return host
    try:
        ipaddress.ip_address(host)
    except ValueError:
        pass
    else:
        return host
    try:
        return registrable_domain(host)
    except ValueError:
        return host


@cache
def _libpsl() -> ctypes.CDLL:
    library = ctypes.util.find_library("psl")
    if library is None:
        raise RuntimeError("libpsl is required to compute registrable domains")
    psl = ctypes.CDLL(library)
    psl.psl_builtin.restype = ctypes.c_void_p
    psl.psl_registrable_domain.argtypes = (ctypes.c_void_p, ctypes.c_char_p)
    psl.psl_registrable_domain.restype = ctypes.c_char_p
    return psl


def registrable_domain(hostname: str) -> str:
    """Return a hostname's eTLD+1 according to the public suffix list."""
    normalized = hostname.rstrip(".").lower().encode("idna")
    psl = _libpsl()
    found = psl.psl_registrable_domain(psl.psl_builtin(), normalized)
    if found is None:
        raise ValueError(f"{hostname!r} has no registrable domain")
    return found.decode("ascii")


def owning_domain(host: str, known: set[str]) -> str | None:
    """The known record a host belongs to, if any."""
    identity = site_identity(host)
    if identity in known:
        return identity
    stripped = host.lstrip(".").lower()
    if stripped in known:
        return stripped
    for domain in known:
        if stripped == domain or stripped.endswith(f".{domain}"):
            return domain
    return None


def playwright_cookie(cookie: Mapping[str, Any]) -> dict[str, Any]:
    """The Playwright cookie shape, accepting either wire alias."""
    converted: dict[str, Any] = {
        "name": cookie["name"],
        "value": cookie["value"],
        "domain": cookie["domain"],
        "path": cookie.get("path", "/"),
        "expires": cookie["expires"]
        if cookie.get("expires") is not None
        else SESSION_COOKIE_EXPIRES,
        "httpOnly": bool(cookie.get("httpOnly", cookie.get("http_only", False))),
        "secure": bool(cookie.get("secure", False)),
    }
    same_site = cookie.get("sameSite", cookie.get("same_site"))
    if same_site:
        converted["sameSite"] = same_site
    partition = cookie.get("partitionKey", cookie.get("partition_key"))
    if partition is not None:
        converted["partitionKey"] = partition
    return converted


def seed_script(auth_states: Sequence[Mapping[str, Any]]) -> str:
    """Init script that fills missing localStorage and sessionStorage keys."""
    local_by_origin: dict[str, list[dict[str, str]]] = {}
    session_by_origin: dict[str, list[dict[str, str]]] = {}
    for state in auth_states:
        for origin in state.get("origins") or []:
            local_by_origin.setdefault(origin["origin"], []).extend(
                {"name": item["name"], "value": item["value"]}
                for item in origin.get("local_storage") or []
            )
        for origin in state.get("session_storage") or []:
            session_by_origin.setdefault(origin["origin"], []).extend(
                {"name": item["name"], "value": item["value"]}
                for item in origin.get("items") or []
            )
    payload = json.dumps(
        {"local": local_by_origin, "session": session_by_origin},
        separators=(",", ":"),
    )
    return f"""(() => {{
  const stores = {payload};
  const origin = location.origin;
  const fill = (storage, items) => {{
    if (!items) return;
    for (const item of items) {{
      try {{
        if (storage.getItem(item.name) === null) storage.setItem(item.name, item.value);
      }} catch {{}}
    }}
  }};
  try {{ fill(localStorage, stores.local[origin]); }} catch {{}}
  try {{ fill(sessionStorage, stores.session[origin]); }} catch {{}}
}})();"""


def inject(context: BrowserContext, auth_states: Sequence[Mapping[str, Any]]) -> None:
    """Load every returned Auth State into a just-opened browser context."""
    cookies = [
        playwright_cookie(cookie)
        for state in auth_states
        for cookie in state.get("cookies") or []
    ]
    if cookies:
        context.add_cookies(cast(Any, cookies))
    if auth_states:
        context.add_init_script(seed_script(auth_states))


def empty_state(domain: str) -> dict[str, Any]:
    return {"domain": domain, "cookies": [], "origins": [], "session_storage": []}


def wire_cookie(cookie: Mapping[str, Any]) -> dict[str, Any]:
    converted: dict[str, Any] = {
        "name": cookie["name"],
        "value": cookie["value"],
        "domain": cookie["domain"],
        "path": cookie.get("path", "/"),
        "httpOnly": bool(cookie.get("httpOnly", False)),
        "secure": bool(cookie.get("secure", False)),
    }
    if (
        cookie.get("expires") is not None
        and cookie["expires"] != SESSION_COOKIE_EXPIRES
    ):
        converted["expires"] = cookie["expires"]
    if cookie.get("sameSite"):
        converted["sameSite"] = cookie["sameSite"]
    if cookie.get("partitionKey") is not None:
        converted["partitionKey"] = cookie["partitionKey"]
    return converted


def collect_session_storage(
    context: BrowserContext, extra_origins: Sequence[str]
) -> dict[str, list[dict[str, str]]]:
    """Read sessionStorage from open pages, then a scratch tab for other origins."""
    collected: dict[str, list[dict[str, str]]] = {}

    def read(page: Page) -> None:
        try:
            origin = page.evaluate("() => location.origin")
            items = page.evaluate(
                """() => Object.entries(sessionStorage).map(
                     ([name, value]) => ({name, value})
                   )"""
            )
        except Exception:
            return
        if isinstance(origin, str) and origin.startswith("http"):
            collected[origin] = list(items or [])

    for page in context.pages:
        read(page)
        for frame in page.frames:
            if frame == page.main_frame:
                continue
            try:
                origin = frame.evaluate("() => location.origin")
                items = frame.evaluate(
                    """() => Object.entries(sessionStorage).map(
                         ([name, value]) => ({name, value})
                       )"""
                )
            except Exception:
                continue
            if isinstance(origin, str) and origin.startswith("http"):
                collected[origin] = list(items or [])

    missing = [origin for origin in extra_origins if origin not in collected]
    if not missing:
        return collected
    scratch = context.new_page()
    try:
        for origin in missing:
            try:
                scratch.goto(origin, wait_until="domcontentloaded")
            except Exception:
                continue
            read(scratch)
    finally:
        scratch.close()
    return collected


def capture(
    context: BrowserContext, known_domains: set[str]
) -> tuple[list[dict[str, Any]], list[str]]:
    """Group the context's cookies and storage into Auth State blobs."""
    raw = context.storage_state()
    known_origins = [
        origin["origin"]
        for origin in raw.get("origins") or []
        if isinstance(origin, dict) and origin.get("origin")
    ]
    session_by_origin = collect_session_storage(context, known_origins)
    grouped: dict[str, dict[str, Any]] = {}

    def bucket(host: str) -> str:
        return owning_domain(host, known_domains) or site_identity(host)

    for cookie in raw.get("cookies") or []:
        domain = bucket(str(cookie.get("domain") or ""))
        if not domain:
            continue
        grouped.setdefault(domain, empty_state(domain))
        grouped[domain]["cookies"].append(wire_cookie(cookie))

    for origin_entry in raw.get("origins") or []:
        origin = str(origin_entry.get("origin") or "")
        host = urlparse(origin).hostname or ""
        domain = bucket(host)
        if not domain:
            continue
        grouped.setdefault(domain, empty_state(domain))
        grouped[domain]["origins"].append(
            {
                "origin": origin,
                "local_storage": [
                    {"name": item["name"], "value": item["value"]}
                    for item in origin_entry.get("localStorage") or []
                ],
            }
        )

    for origin, items in session_by_origin.items():
        host = urlparse(origin).hostname or ""
        domain = bucket(host)
        if not domain:
            continue
        grouped.setdefault(domain, empty_state(domain))
        grouped[domain]["session_storage"].append({"origin": origin, "items": items})

    states = [grouped[domain] for domain in sorted(grouped)]
    new_domains = sorted(
        domain
        for domain, state in grouped.items()
        if domain not in known_domains
        and (state["cookies"] or state["origins"] or state["session_storage"])
    )
    return states, new_domains


def existing_and_consented(
    states: Sequence[Mapping[str, Any]],
    known_domains: set[str],
    consented: Sequence[str],
) -> list[Mapping[str, Any]]:
    allowed = known_domains | set(consented)
    return [state for state in states if state["domain"] in allowed]


class HttpCredentials:
    """The internal credential routes, authenticated with the shared token."""

    def __init__(self, run_id: UUID) -> None:
        self.run_id = run_id

    def fetch(self) -> CredentialSet:
        payload = self._request("GET", "credentials")
        secrets = {
            str(item["variable_name"]): str(item["value"])
            for item in payload.get("secrets") or []
        }
        return CredentialSet(
            secrets=secrets, auth_states=list(payload.get("auth_states") or [])
        )

    def consents(self) -> list[str]:
        payload = self._request("GET", "auth-state-consents")
        return [str(domain) for domain in payload.get("domains") or []]

    def write_back(
        self,
        states: Sequence[Mapping[str, Any]],
        new_candidates: Sequence[str],
    ) -> None:
        self._request(
            "POST",
            "auth-states",
            {"states": list(states), "new_candidates": list(new_candidates)},
        )

    def _request(
        self, method: str, suffix: str, body: Mapping[str, Any] | None = None
    ) -> dict[str, Any]:
        base = environ[API_URL_VARIABLE].rstrip("/")
        token = environ[INTERNAL_TOKEN_VARIABLE]
        data = None if body is None else json.dumps(body).encode()
        request = Request(
            f"{base}/internal/runs/{self.run_id}/{suffix}",
            data=data,
            headers={
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json",
            },
            method=method,
        )
        try:
            with urlopen(request, timeout=5) as response:
                raw = response.read()
        except HTTPError as error:
            payload = _error_payload(error)
            if error.code == 409 and payload.get("code") == "missing_secret":
                names = payload.get("variable_names") or []
                raise MissingSecret(
                    [str(name) for name in names] if isinstance(names, list) else []
                ) from error
            raise
        if not raw:
            return {}
        parsed = json.loads(raw)
        return parsed if isinstance(parsed, dict) else {}


def _error_payload(error: HTTPError) -> dict[str, Any]:
    try:
        parsed = json.loads(error.read())
    except Exception:
        return {}
    return parsed if isinstance(parsed, dict) else {}
