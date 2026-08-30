import pytest
from step_by_step_core.objects import artifact_bucket, object_store, signing_store


@pytest.fixture(autouse=True)
def two_endpoints(monkeypatch: pytest.MonkeyPatch) -> None:
    object_store.cache_clear()
    signing_store.cache_clear()
    monkeypatch.setenv("S3_ENDPOINT_URL", "http://garage:3900")
    monkeypatch.setenv("S3_PUBLIC_ENDPOINT", "https://artifacts.example")
    monkeypatch.setenv("S3_ACCESS_KEY_ID", "key")
    monkeypatch.setenv("S3_SECRET_ACCESS_KEY", "secret")
    monkeypatch.setenv("S3_BUCKET", "artifacts")
    monkeypatch.setenv("S3_REGION", "garage")


def test_objects_are_read_and_written_at_the_internal_endpoint() -> None:
    assert object_store().meta.endpoint_url == "http://garage:3900"


def test_a_signed_url_points_at_the_public_endpoint() -> None:
    url = signing_store().generate_presigned_url(
        "get_object",
        Params={"Bucket": artifact_bucket(), "Key": "run/1/shot.png"},
        ExpiresIn=60,
    )

    assert url.startswith("https://artifacts.example/artifacts/run/1/shot.png?")


def test_the_bucket_comes_from_the_environment() -> None:
    assert artifact_bucket() == "artifacts"


def test_a_missing_endpoint_fails_loudly(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("S3_PUBLIC_ENDPOINT")

    with pytest.raises(KeyError, match="S3_PUBLIC_ENDPOINT"):
        signing_store()
