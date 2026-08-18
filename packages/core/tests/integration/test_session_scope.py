"""The session scope a Worker opens, against the real Postgres."""

import pytest
from sqlalchemy import text
from step_by_step_core.db import session_scope

pytestmark = pytest.mark.integration


def test_a_worker_reaches_the_database_through_the_session_scope() -> None:
    with session_scope() as session:
        answer = session.execute(text("SELECT 1")).scalar_one()

    assert answer == 1
