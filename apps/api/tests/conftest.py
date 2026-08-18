"""What every backend test shares.

Starting the app configures logging for the whole process — one handler on the
root logger, from `step_by_step_api.logs` — and a handler keeps the stream it
was built with. A test that started the app and left its handler behind would
hand the next test a stream pytest has already taken back, so each test takes
what it added away again.
"""

import logging
from collections.abc import Iterator

import pytest
from step_by_step_api.logs import HANDLER_NAME


@pytest.fixture(autouse=True)
def application_logging_stays_in_its_test() -> Iterator[None]:
    """Whatever starting the app put on the root logger, off it again."""
    root = logging.getLogger()
    level = root.level
    yield
    root.handlers[:] = [
        handler for handler in root.handlers if handler.get_name() != HANDLER_NAME
    ]
    root.setLevel(level)
