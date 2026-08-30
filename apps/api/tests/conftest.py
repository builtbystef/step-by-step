import logging
from collections.abc import Iterator

import pytest
from step_by_step_api.logs import HANDLER_NAME


@pytest.fixture(autouse=True)
def application_logging_stays_in_its_test() -> Iterator[None]:
    root = logging.getLogger()
    level = root.level
    yield
    root.handlers[:] = [
        handler for handler in root.handlers if handler.get_name() != HANDLER_NAME
    ]
    root.setLevel(level)
