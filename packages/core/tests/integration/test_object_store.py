import time
import urllib.error
import urllib.request

import pytest
from step_by_step_core.objects import artifact_bucket, object_store, signing_store

pytestmark = pytest.mark.integration


def fetch(url: str) -> tuple[int, bytes]:
    try:
        with urllib.request.urlopen(url) as response:
            return response.status, response.read()
    except urllib.error.HTTPError as refused:
        return refused.code, refused.read()


def test_an_object_written_through_the_store_reads_back(object_key: str) -> None:
    object_store().put_object(
        Bucket=artifact_bucket(),
        Key=object_key,
        Body=b"step by step",
        ContentType="text/plain",
    )

    stored = object_store().get_object(Bucket=artifact_bucket(), Key=object_key)

    assert stored["Body"].read() == b"step by step"


def test_a_presigned_url_fetches_the_object_from_outside_the_stack(
    object_key: str,
) -> None:
    object_store().put_object(
        Bucket=artifact_bucket(), Key=object_key, Body=b"step by step"
    )

    url = signing_store().generate_presigned_url(
        "get_object",
        Params={"Bucket": artifact_bucket(), "Key": object_key},
        ExpiresIn=60,
    )

    assert fetch(url) == (200, b"step by step")


def test_a_presigned_url_stops_working_once_it_expires(object_key: str) -> None:
    object_store().put_object(
        Bucket=artifact_bucket(), Key=object_key, Body=b"step by step"
    )
    url = signing_store().generate_presigned_url(
        "get_object",
        Params={"Bucket": artifact_bucket(), "Key": object_key},
        ExpiresIn=1,
    )

    time.sleep(2)
    status, body = fetch(url)

    assert status >= 400
    assert body != b"step by step"
