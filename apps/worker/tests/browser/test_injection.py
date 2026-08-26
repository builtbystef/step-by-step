"""Auth State injection and write-back, observed through the executor seam."""

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import pytest
from step_by_step_worker.credentials import CredentialSet, MissingSecret
from step_by_step_worker.executor import execute
from test_executor import (
    RecordedRun,
    step,
    take_control_then_hand_back,
    target,
    work,
)

pytestmark = pytest.mark.browser


@dataclass
class RecordedCredentials:
    secrets: dict[str, str] = field(default_factory=dict)
    auth_states: list[dict[str, Any]] = field(default_factory=list)
    consented: list[str] = field(default_factory=list)
    missing: list[str] | None = None
    drop_after_fetch: bool = False
    fetches: int = 0
    writes: list[tuple[list[Mapping[str, Any]], list[str]]] = field(
        default_factory=list
    )

    def fetch(self) -> CredentialSet:
        self.fetches += 1
        if self.missing is not None:
            raise MissingSecret(self.missing)
        loaded = CredentialSet(secrets=dict(self.secrets), auth_states=self.auth_states)
        if self.drop_after_fetch:
            self.missing = list(self.secrets) or ["password"]
        return loaded

    def consents(self) -> list[str]:
        return list(self.consented)

    def write_back(
        self, states: Sequence[Mapping[str, Any]], new_candidates: Sequence[str]
    ) -> None:
        self.writes.append((list(states), list(new_candidates)))


def seeded_state(origin: str) -> dict[str, Any]:
    host = urlparse(origin).hostname
    return {
        "domain": host,
        "cookies": [
            {
                "name": "session",
                "value": "seeded",
                "domain": host,
                "path": "/",
                "httpOnly": False,
                "secure": False,
                "sameSite": "Lax",
            }
        ],
        "origins": [
            {
                "origin": origin,
                "local_storage": [{"name": "token", "value": "local-seed"}],
            }
        ],
        "session_storage": [
            {
                "origin": origin,
                "items": [{"name": "state", "value": "session-seed"}],
            }
        ],
    }


def extract(label: str, testid: str) -> dict[str, Any]:
    return step(
        "extract",
        label,
        {
            "target": target(("testid", testid)),
            "outputName": testid,
            "mode": "scalar",
        },
    )


def test_run_starts_signed_in_from_seeded_auth_state(
    playwright_driver: Any, fixture_site: str, tmp_path: Path
) -> None:
    recorded = RecordedRun()
    credentials = RecordedCredentials(auth_states=[seeded_state(fixture_site)])
    run = work(
        {
            "variables": [],
            "steps": [
                step(
                    "navigate",
                    "Open seeded site",
                    {"url": f"{fixture_site}/signed-in.html"},
                ),
                extract("Read signed-in marker", "status"),
                extract("Read sessionStorage marker", "session"),
            ],
        }
    )

    execute(
        run,
        playwright_driver.chromium,
        recorded,
        tmp_path,
        headless=True,
        credentials=credentials,
    )

    assert credentials.fetches == 1
    assert [result.status for result in recorded.results] == [
        "passed",
        "passed",
        "passed",
    ]
    assert recorded.results[1].extracted_value == "signed-in"
    assert recorded.results[2].extracted_value == "visible"
    assert recorded.terminal is not None
    assert recorded.terminal[:2] == ("succeeded", None)


def cookie_value(states: list[Mapping[str, Any]], name: str) -> str | None:
    for state in states:
        for cookie in state.get("cookies") or []:
            if cookie["name"] == name:
                return str(cookie["value"])
    return None


def storage_value(
    states: list[Mapping[str, Any]], field: str, items_key: str, name: str
) -> str | None:
    for state in states:
        for origin in state.get(field) or []:
            for item in origin.get(items_key) or []:
                if item["name"] == name:
                    return str(item["value"])
    return None


def test_successful_run_writes_back_refreshed_session(
    playwright_driver: Any, fixture_site: str, tmp_path: Path
) -> None:
    recorded = RecordedRun()
    credentials = RecordedCredentials(auth_states=[seeded_state(fixture_site)])
    run = work(
        {
            "variables": [],
            "steps": [
                step(
                    "navigate",
                    "Open seeded site",
                    {"url": f"{fixture_site}/signed-in.html"},
                )
            ],
        }
    )

    execute(
        run,
        playwright_driver.chromium,
        recorded,
        tmp_path,
        headless=True,
        credentials=credentials,
    )

    assert recorded.terminal is not None
    assert recorded.terminal[:2] == ("succeeded", None)
    assert len(credentials.writes) == 1
    states, new_candidates = credentials.writes[0]
    assert new_candidates == []
    assert cookie_value(list(states), "session") == "refreshed"
    assert storage_value(list(states), "origins", "local_storage", "token") == (
        "local-refreshed"
    )
    assert storage_value(list(states), "session_storage", "items", "state") == (
        "session-refreshed"
    )


def test_failed_run_does_not_write_back(
    playwright_driver: Any, fixture_site: str, tmp_path: Path
) -> None:
    recorded = RecordedRun()
    credentials = RecordedCredentials(auth_states=[seeded_state(fixture_site)])
    run = work(
        {
            "variables": [],
            "steps": [
                step(
                    "navigate",
                    "Open seeded site",
                    {"url": f"{fixture_site}/signed-in.html"},
                ),
                step(
                    "click",
                    "Missing",
                    {"target": target(("testid", "gone"))},
                    timeoutMs=5,
                ),
            ],
        }
    )

    execute(
        run,
        playwright_driver.chromium,
        recorded,
        tmp_path,
        headless=True,
        credentials=credentials,
    )

    assert recorded.terminal is not None
    assert recorded.terminal[:2] == ("failed", "step_failed")
    assert credentials.writes == []


def test_handback_writes_back_even_when_the_run_later_fails(
    playwright_driver: Any, fixture_site: str, tmp_path: Path
) -> None:
    recorded = RecordedRun()
    credentials = RecordedCredentials(auth_states=[seeded_state(fixture_site)])
    run = work(
        {
            "variables": [],
            "steps": [
                step(
                    "navigate",
                    "Open seeded site",
                    {"url": f"{fixture_site}/signed-in.html"},
                ),
                step("pause-for-takeover", "Refresh the login", {}),
                step(
                    "click",
                    "Missing",
                    {"target": target(("testid", "gone"))},
                    timeoutMs=5,
                ),
            ],
        }
    )

    execute(
        run,
        playwright_driver.chromium,
        recorded,
        tmp_path,
        headless=True,
        control=take_control_then_hand_back(recorded),
        credentials=credentials,
    )

    assert recorded.terminal is not None
    assert recorded.terminal[:2] == ("failed", "step_failed")
    assert len(credentials.writes) == 1
    states, _ = credentials.writes[0]
    assert cookie_value(list(states), "session") == "refreshed"
    assert storage_value(list(states), "origins", "local_storage", "token") == (
        "local-refreshed"
    )
    assert storage_value(list(states), "session_storage", "items", "state") == (
        "session-refreshed"
    )


def takeover_with_new_domain(
    fixture_site: str, other_site: str, extra_steps: list[dict[str, Any]]
) -> dict[str, Any]:
    return {
        "variables": [],
        "steps": [
            step(
                "navigate",
                "Open seeded site with a new login frame",
                {
                    "url": (
                        f"{fixture_site}/signed-in.html"
                        f"?also={other_site}/new-login.html"
                    )
                },
            ),
            step(
                "click",
                "Open the new site",
                {
                    "target": target(("testid", "other")),
                    "assertedNavigation": True,
                },
            ),
            step("pause-for-takeover", "Keep the new login?", {}),
            *extra_steps,
        ],
    }


def test_consented_new_domain_is_stored_on_final_write_back(
    playwright_driver: Any, fixture_site: str, other_site: str, tmp_path: Path
) -> None:
    recorded = RecordedRun()
    new_domain = urlparse(other_site).hostname or ""
    credentials = RecordedCredentials(
        auth_states=[seeded_state(fixture_site)], consented=[new_domain]
    )
    run = work(takeover_with_new_domain(fixture_site, other_site, []))

    execute(
        run,
        playwright_driver.chromium,
        recorded,
        tmp_path,
        headless=True,
        control=take_control_then_hand_back(recorded),
        credentials=credentials,
    )

    assert recorded.terminal is not None
    assert recorded.terminal[:2] == ("succeeded", None)
    assert len(credentials.writes) == 2
    handback_states, handback_candidates = credentials.writes[0]
    assert new_domain in handback_candidates
    assert all(state["domain"] != new_domain for state in handback_states)
    final_states, final_candidates = credentials.writes[1]
    assert final_candidates == []
    assert (
        cookie_value(
            [state for state in final_states if state["domain"] == new_domain],
            "session",
        )
        == "new-login"
    )


def test_unconsented_new_domain_never_leaves_the_worker(
    playwright_driver: Any, fixture_site: str, other_site: str, tmp_path: Path
) -> None:
    recorded = RecordedRun()
    new_domain = urlparse(other_site).hostname or ""
    credentials = RecordedCredentials(auth_states=[seeded_state(fixture_site)])
    run = work(takeover_with_new_domain(fixture_site, other_site, []))

    execute(
        run,
        playwright_driver.chromium,
        recorded,
        tmp_path,
        headless=True,
        control=take_control_then_hand_back(recorded),
        credentials=credentials,
    )

    assert recorded.terminal is not None
    assert recorded.terminal[:2] == ("succeeded", None)
    assert len(credentials.writes) == 2
    handback_states, handback_candidates = credentials.writes[0]
    assert new_domain in handback_candidates
    final_states, _ = credentials.writes[1]
    for states in (handback_states, final_states):
        assert all(state["domain"] != new_domain for state in states)


def test_secrets_are_fetched_once_and_held_for_the_run(
    playwright_driver: Any, fixture_site: str, tmp_path: Path
) -> None:
    recorded = RecordedRun()
    credentials = RecordedCredentials(
        secrets={"password": "held-secret"}, drop_after_fetch=True
    )
    run = work(
        {
            "variables": [{"name": "password", "secret": True}],
            "steps": [
                step(
                    "navigate",
                    "Open form",
                    {"url": f"{fixture_site}/executor.html"},
                ),
                step(
                    "type",
                    "Type the secret",
                    {
                        "target": target(("testid", "name")),
                        "value": "{{password}}",
                    },
                ),
                step("click", "Save", {"target": target(("testid", "save"))}),
                step(
                    "extract",
                    "Read saved value",
                    {
                        "target": target(("css", "body")),
                        "outputName": "saved",
                        "mode": "scalar",
                        "attribute": "data-saved",
                    },
                ),
            ],
        }
    )

    execute(
        run,
        playwright_driver.chromium,
        recorded,
        tmp_path,
        headless=True,
        credentials=credentials,
    )

    assert credentials.fetches == 1
    assert [result.status for result in recorded.results] == [
        "passed",
        "passed",
        "passed",
        "passed",
    ]
    assert recorded.results[3].extracted_value == "held-secret"
    assert recorded.terminal is not None
    assert recorded.terminal[:2] == ("succeeded", None)

    next_recorded = RecordedRun()
    execute(
        work(
            {
                "variables": [{"name": "password", "secret": True}],
                "steps": [
                    step(
                        "navigate",
                        "Would not run",
                        {"url": f"{fixture_site}/executor.html"},
                    )
                ],
            }
        ),
        playwright_driver.chromium,
        next_recorded,
        tmp_path,
        headless=True,
        credentials=credentials,
    )

    assert next_recorded.terminal is not None
    assert next_recorded.terminal[:2] == ("failed", "missing_secret")
    assert [result.status for result in next_recorded.results] == ["skipped"]
