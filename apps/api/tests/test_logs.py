"""Where the backend's own log records go.

uvicorn configures handlers for its `uvicorn*` loggers and none for the root,
so an application record at INFO is written to a logger with nothing attached
and dropped. The console mailer's message is such a record, and on a default
dev instance the Sign-in Code inside it is the only way in — so this is tested
at the seam that broke: the app started the way uvicorn starts it, and a
mailed message read off the process's own stdout.

Nothing here needs a service; the lifespan is the one the test client runs.
"""

import logging
import logging.config
from base64 import b64encode
from collections.abc import Iterator

import pytest
import uvicorn.config
from fastapi.testclient import TestClient
from step_by_step_api.envelope import KEY_BYTES, master_key
from step_by_step_api.logs import HANDLER_NAME
from step_by_step_api.mail import mailer, send
from step_by_step_api.main import app

VALID_KEY = b64encode(bytes(range(KEY_BYTES))).decode()

UVICORN_LOGGERS = ("uvicorn", "uvicorn.error", "uvicorn.access")


@pytest.fixture(autouse=True)
def a_bootable_instance(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    """The environment a default dev instance boots with, and no cached boot."""
    monkeypatch.setenv("STEPBYSTEP_MASTER_KEY", VALID_KEY)
    monkeypatch.setenv("MAILER", "console")
    master_key.cache_clear()
    mailer.cache_clear()
    yield
    master_key.cache_clear()
    mailer.cache_clear()


@pytest.fixture(autouse=True)
def uvicorns_logging_stays_in_its_test() -> Iterator[None]:
    """One test configures uvicorn's loggers the way uvicorn does; only it.

    The root logger is `conftest.py`'s to clean up, and it does that for every
    test in the package — this is the one place that also touches uvicorn's.
    """
    was = [
        (logging.getLogger(name), logging.getLogger(name).handlers[:])
        for name in UVICORN_LOGGERS
    ]
    yield
    for logger, handlers in was:
        logger.handlers[:] = handlers


def test_a_mailed_message_reaches_stdout_when_the_app_has_started(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """The bug: without a handler on the root, this went nowhere."""
    with TestClient(app):
        send(to="ada@example.com", subject="Your sign-in code", text="It is 123456.")

    printed = capsys.readouterr().out
    assert "ada@example.com" in printed
    assert "It is 123456." in printed


def test_a_mailed_message_is_printed_once_however_often_the_app_starts(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """`--reload` and the test client both start the app more than once."""
    with TestClient(app):
        pass
    with TestClient(app):
        send(to="ada@example.com", subject="Your sign-in code", text="It is 123456.")

    assert capsys.readouterr().out.count("It is 123456.") == 1


def test_uvicorns_own_records_are_neither_silenced_nor_doubled(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Production order: uvicorn configures its logging, then imports the app."""
    logging.config.dictConfig(uvicorn.config.LOGGING_CONFIG)

    with TestClient(app):
        logging.getLogger("uvicorn.error").info("Application startup complete.")
        # The five arguments uvicorn's own access formatter reads.
        logging.getLogger("uvicorn.access").info(
            '%s - "%s %s HTTP/%s" %d',
            "127.0.0.1:57000",
            "GET",
            "/api/health",
            "1.1",
            200,
        )

    printed = capsys.readouterr()
    written = printed.out + printed.err
    assert written.count("Application startup complete.") == 1
    assert written.count("GET /api/health HTTP/1.1") == 1


def test_the_application_handler_is_the_only_one_the_app_adds() -> None:
    """One place configures logging, so one handler carries every call site."""
    with TestClient(app):
        pass

    root = logging.getLogger()
    assert [handler.get_name() for handler in root.handlers].count(HANDLER_NAME) == 1
    for name in UVICORN_LOGGERS:
        assert not any(
            handler.get_name() == HANDLER_NAME
            for handler in logging.getLogger(name).handlers
        )
