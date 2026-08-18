"""What a Worker proves before it will take a Run.

A Worker that cannot reach Redis, Postgres, its display, its VNC server, or
the Artifact store must not sit in the pool looking healthy. It says what it
found, and it refuses to start.
"""

import logging

import pytest
from step_by_step_worker.readiness import NotReady, report


def test_every_check_reports_what_it_found(caplog: pytest.LogCaptureFixture) -> None:
    with caplog.at_level(logging.INFO):
        report({"redis": lambda: "PONG", "display": lambda: ":99, 1280x1024"})

    assert "redis: PONG" in caplog.text
    assert "display: :99, 1280x1024" in caplog.text


def test_a_worker_that_fails_a_check_refuses_to_start() -> None:
    def unreachable() -> str:
        raise ConnectionError("connection refused")

    with pytest.raises(NotReady):
        report({"redis": unreachable})


def test_the_failure_names_the_check_and_its_reason(
    caplog: pytest.LogCaptureFixture,
) -> None:
    def unreachable() -> str:
        raise ConnectionError("connection refused")

    with pytest.raises(NotReady), caplog.at_level(logging.ERROR):
        report({"redis": unreachable})

    assert "redis: connection refused" in caplog.text


def test_every_check_runs_even_after_one_fails(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """One boot shows every problem, rather than one problem per boot."""

    def unreachable() -> str:
        raise ConnectionError("connection refused")

    with pytest.raises(NotReady), caplog.at_level(logging.INFO):
        report({"redis": unreachable, "database": lambda: "PostgreSQL 17"})

    assert "database: PostgreSQL 17" in caplog.text
