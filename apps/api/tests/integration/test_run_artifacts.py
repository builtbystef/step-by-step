"""Artifact download, ownership, and Run deletion against Postgres and Garage."""

import time
import urllib.error
import urllib.request
from collections.abc import Iterator
from dataclasses import dataclass
from uuid import UUID, uuid4

import pytest
from botocore.exceptions import ClientError
from conftest import Account, join
from sqlalchemy import func, select
from step_by_step_api import clock
from step_by_step_api.runs import routes as run_routes
from step_by_step_api.runs.models import (
    Artifact,
    ArtifactKind,
    LogLevel,
    Run,
    RunLogLine,
    RunStatus,
    StepResult,
    StepResultStatus,
)
from step_by_step_core.db import session_scope
from step_by_step_core.objects import artifact_bucket, object_store, signing_store
from step_by_step_worker.store import PostgresRunStore
from test_runs import NewAccount, published_workflow, start

pytestmark = pytest.mark.integration

FIXTURE_BYTES = b"fixture-report-body\n"


@pytest.fixture(autouse=True)
def real_object_clients() -> Iterator[None]:
    object_store.cache_clear()
    signing_store.cache_clear()
    yield
    object_store.cache_clear()
    signing_store.cache_clear()


@pytest.fixture
def owned_keys() -> Iterator[list[str]]:
    keys: list[str] = []
    yield keys
    for key in keys:
        object_store().delete_object(Bucket=artifact_bucket(), Key=key)


def fetch(url: str) -> tuple[int, bytes]:
    try:
        with urllib.request.urlopen(url) as response:
            return response.status, response.read()
    except urllib.error.HTTPError as refused:
        return refused.code, refused.read()


def object_missing(key: str) -> bool:
    try:
        object_store().get_object(Bucket=artifact_bucket(), Key=key)
    except ClientError as error:
        return error.response["ResponseMetadata"]["HTTPStatusCode"] == 404
    return False


def put_object(key: str, body: bytes, content_type: str = "text/plain") -> None:
    object_store().put_object(
        Bucket=artifact_bucket(),
        Key=key,
        Body=body,
        ContentType=content_type,
    )


@dataclass(frozen=True, slots=True)
class SeededArtifact:
    id: UUID
    object_key: str


def seed_artifact(
    run_id: UUID,
    keys: list[str],
    *,
    body: bytes = FIXTURE_BYTES,
    kind: ArtifactKind = ArtifactKind.DOWNLOAD,
    filename: str = "report.txt",
    content_type: str = "text/plain",
    step_id: UUID | None = None,
    index: int = 0,
) -> SeededArtifact:
    artifact_id = uuid4()
    key = f"runs/{run_id}/{artifact_id}/{filename}"
    put_object(key, body, content_type)
    keys.append(key)
    with session_scope() as db:
        db.add(
            Artifact(
                id=artifact_id,
                run_id=run_id,
                step_id=step_id,
                kind=kind,
                object_key=key,
                content_type=content_type,
                size_bytes=len(body),
                index=index,
            )
        )
        db.commit()
    return SeededArtifact(id=artifact_id, object_key=key)


def set_status(run_id: str, status: RunStatus) -> None:
    with session_scope() as db:
        run = db.get(Run, UUID(run_id))
        assert run is not None
        run.status = status
        if status.value not in ("queued", "running", "waiting_for_human"):
            run.ended_at = clock.now()
        db.commit()


def download(account: Account, run_id: str, artifact_id: UUID):
    return account.client.get(
        f"/api/runs/{run_id}/artifacts/{artifact_id}/download",
        follow_redirects=False,
    )


def test_owner_download_redirects_to_a_working_url_that_expires(
    new_account: NewAccount,
    monkeypatch: pytest.MonkeyPatch,
    owned_keys: list[str],
) -> None:
    account = new_account()
    run_id = start(account, published_workflow(account), variables={}).json()["run_id"]
    artifact = seed_artifact(UUID(run_id), owned_keys)
    monkeypatch.setattr(run_routes, "PRESIGN_SECONDS", 1)

    response = download(account, run_id, artifact.id)

    assert response.status_code == 307, response.text
    location = response.headers["location"]
    assert fetch(location) == (200, FIXTURE_BYTES)
    time.sleep(2)
    status, body = fetch(location)
    assert status >= 400
    assert body != FIXTURE_BYTES


def test_another_organizations_download_is_404_and_mints_no_url(
    new_account: NewAccount,
    monkeypatch: pytest.MonkeyPatch,
    owned_keys: list[str],
) -> None:
    owner = new_account()
    stranger = new_account()
    run_id = start(owner, published_workflow(owner), variables={}).json()["run_id"]
    artifact = seed_artifact(UUID(run_id), owned_keys)
    minted: list[str] = []
    original = run_routes.presign_download

    def wrapped(object_key: str, filename: str) -> str:
        minted.append(object_key)
        return original(object_key, filename)

    monkeypatch.setattr(run_routes, "presign_download", wrapped)

    refused = download(stranger, run_id, artifact.id)

    assert refused.status_code == 404
    assert refused.json()["code"] == "run_not_found"
    assert minted == []


def test_any_member_of_the_run_organization_may_download(
    new_account: NewAccount, owned_keys: list[str]
) -> None:
    owner = new_account()
    member = join(owner, new_account())
    run_id = start(owner, published_workflow(owner), variables={}).json()["run_id"]
    artifact = seed_artifact(UUID(run_id), owned_keys)

    response = download(member, run_id, artifact.id)

    assert response.status_code == 307, response.text
    assert fetch(response.headers["location"]) == (200, FIXTURE_BYTES)


def test_deleting_a_running_run_is_conflict(
    new_account: NewAccount, owned_keys: list[str]
) -> None:
    account = new_account()
    run_id = start(account, published_workflow(account), variables={}).json()["run_id"]
    artifact = seed_artifact(UUID(run_id), owned_keys)
    set_status(run_id, RunStatus.RUNNING)

    refused = account.client.delete(f"/api/runs/{run_id}")

    assert refused.status_code == 409
    assert refused.json()["code"] == "run_active"
    assert not object_missing(artifact.object_key)


def test_deleting_a_terminal_run_purges_rows_and_objects(
    new_account: NewAccount, owned_keys: list[str]
) -> None:
    account = new_account()
    run_id = start(account, published_workflow(account), variables={}).json()["run_id"]
    run = UUID(run_id)
    artifact = seed_artifact(run, owned_keys)
    with session_scope() as db:
        db.add(
            StepResult(
                run_id=run,
                step_id=uuid4(),
                position=0,
                status=StepResultStatus.PASSED,
            )
        )
        db.add(
            RunLogLine(
                run_id=run,
                seq=1,
                level=LogLevel.INFO,
                at=clock.now(),
                text="clicked Save",
            )
        )
        db.commit()
    set_status(run_id, RunStatus.SUCCEEDED)

    deleted = account.client.delete(f"/api/runs/{run_id}")

    assert deleted.status_code == 204, deleted.text
    assert account.client.get(f"/api/runs/{run_id}").status_code == 404
    with session_scope() as db:
        assert db.get(Run, run) is None
        assert db.get(Artifact, artifact.id) is None
        assert (
            db.scalar(
                select(func.count())
                .select_from(StepResult)
                .where(StepResult.run_id == run)
            )
            == 0
        )
        assert (
            db.scalar(
                select(func.count())
                .select_from(RunLogLine)
                .where(RunLogLine.run_id == run)
            )
            == 0
        )
    assert object_missing(artifact.object_key)


def test_worker_artifact_insert_is_what_the_download_route_serves(
    new_account: NewAccount, owned_keys: list[str]
) -> None:
    account = new_account()
    run_id = start(account, published_workflow(account), variables={}).json()["run_id"]
    step_id = uuid4()
    store = PostgresRunStore()

    artifact_id = store.add_artifact(
        UUID(run_id),
        kind="download",
        body=FIXTURE_BYTES,
        content_type="text/plain",
        index=0,
        step_id=step_id,
        filename="report.txt",
    )
    owned_keys.append(f"runs/{run_id}/{artifact_id}/report.txt")

    detail = account.client.get(f"/api/runs/{run_id}").json()
    listed = detail["artifacts"]
    assert len(listed) == 1
    assert listed[0]["id"] == str(artifact_id)
    assert listed[0]["kind"] == "download"
    assert listed[0]["step_id"] == str(step_id)
    assert listed[0]["filename"] == "report.txt"
    assert listed[0]["content_type"] == "text/plain"
    response = download(account, run_id, artifact_id)
    assert response.status_code == 307, response.text
    assert fetch(response.headers["location"]) == (200, FIXTURE_BYTES)
