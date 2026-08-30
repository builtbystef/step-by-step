import io
import json
import os
import zipfile
from pathlib import Path
from string import Template
from typing import Any

from step_by_step_api.errors import ApiError

EXTENSION_DIR_VARIABLE = "EXTENSION_DIR"

REPOSITORY_PACKAGE_DIR = Path(__file__).parents[4] / "extension" / "src"

MINIMUM_SUPPORTED_VERSION = "0.1.0"


def package_dir() -> Path:
    return Path(os.environ.get(EXTENSION_DIR_VARIABLE) or REPOSITORY_PACKAGE_DIR)


def manifest() -> dict[str, Any]:
    try:
        read = json.loads((package_dir() / "manifest.json").read_text())
    except (OSError, json.JSONDecodeError) as missing:
        raise ApiError(
            503,
            "extension_unavailable",
            f"No extension build at {package_dir()}; set {EXTENSION_DIR_VARIABLE}.",
        ) from missing
    if not isinstance(read, dict):
        raise ApiError(
            503, "extension_unavailable", "The extension manifest is not an object."
        )
    return read


def current_version() -> str:
    return str(manifest()["version"])


def archive() -> bytes:
    root = package_dir()
    current_version()
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as building:
        for file in sorted(path for path in root.rglob("*") if path.is_file()):
            building.write(file, file.relative_to(root).as_posix())
    return buffer.getvalue()


INSTALL_PAGE_TEMPLATE = Path(__file__).parent / "install.html"


def install_page(current: str) -> str:
    written = Template(INSTALL_PAGE_TEMPLATE.read_text())
    return written.substitute(version=current, chrome=minimum_chrome_version())


def minimum_chrome_version() -> str:
    return str(manifest().get("minimum_chrome_version", ""))
