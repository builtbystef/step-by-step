import json
import zipfile
from io import BytesIO
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from step_by_step_api.extension.package import (
    EXTENSION_DIR_VARIABLE,
    MINIMUM_SUPPORTED_VERSION,
    package_dir,
)
from step_by_step_api.main import app

client = TestClient(app)

MANIFEST = json.loads((package_dir() / "manifest.json").read_text())


def test_the_version_endpoint_reports_the_build_this_instance_serves() -> None:
    response = client.get("/api/extension/version")

    assert response.status_code == 200
    assert response.json() == {
        "current": MANIFEST["version"],
        "minimum_supported": MINIMUM_SUPPORTED_VERSION,
    }


def test_the_zip_is_the_paired_build_itself() -> None:
    response = client.get("/extension.zip")

    assert response.status_code == 200
    assert response.headers["content-type"] == "application/zip"
    assert MANIFEST["version"] in response.headers["content-disposition"]

    package = zipfile.ZipFile(BytesIO(response.content))
    assert package.testzip() is None
    assert json.loads(package.read("manifest.json")) == MANIFEST
    assert "service-worker.js" in package.namelist()
    assert "lib/handshake.js" in package.namelist()


def test_the_install_page_describes_the_unpacked_sequence() -> None:
    response = client.get("/extension")
    page = response.text

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/html")
    assert "/extension.zip" in page
    for step in ("chrome://extensions", "Developer mode", "Load unpacked"):
        assert step in page
    assert MANIFEST["version"] in page


def test_the_install_page_carries_the_enterprise_policy_note() -> None:
    assert "policy" in client.get("/extension").text


def test_an_instance_without_the_package_says_so_rather_than_serving_half_of_it(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv(EXTENSION_DIR_VARIABLE, str(tmp_path / "nothing-here"))

    for path in ("/api/extension/version", "/extension.zip", "/extension"):
        response = client.get(path)
        assert response.status_code == 503, path
        assert response.json()["code"] == "extension_unavailable", path
