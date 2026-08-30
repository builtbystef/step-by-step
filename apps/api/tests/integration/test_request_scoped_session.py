from collections.abc import Iterator

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from pydantic import BaseModel
from sqlalchemy import Column, Integer, MetaData, Table, Text, insert, select
from step_by_step_api.db import SessionDep, get_engine

pytestmark = pytest.mark.integration

probes = Table(
    "session_probes",
    MetaData(),
    Column("id", Integer, primary_key=True),
    Column("body", Text, nullable=False),
)


class Probe(BaseModel):
    body: str


@pytest.fixture
def client() -> Iterator[TestClient]:
    probes.create(get_engine())
    app = FastAPI()

    @app.post("/probes")
    def write_probe(probe: Probe, session: SessionDep) -> int:
        written = session.execute(
            insert(probes).values(body=probe.body).returning(probes.c.id)
        )
        probe_id = written.scalar_one()
        session.commit()
        return probe_id

    @app.get("/probes/{probe_id}")
    def read_probe(probe_id: int, session: SessionDep) -> Probe:
        body = session.execute(
            select(probes.c.body).where(probes.c.id == probe_id)
        ).scalar_one()
        return Probe(body=body)

    yield TestClient(app)
    probes.drop(get_engine())


def test_a_row_written_in_one_request_is_read_back_in_the_next(
    client: TestClient,
) -> None:
    written = client.post("/probes", json={"body": "step by step"})
    assert written.status_code == 200

    read = client.get(f"/probes/{written.json()}")

    assert read.status_code == 200
    assert read.json() == {"body": "step by step"}
