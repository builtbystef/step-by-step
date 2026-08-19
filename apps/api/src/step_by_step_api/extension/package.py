"""The extension build this instance serves, and the two things it is asked for.

v1 ships unpacked (n52g83): no Chrome Web Store listing, and no self-hosted
`.crx` with an update feed, because an off-store `.crx` installs on Linux
alone. What an instance has instead is the build that came with it — one
directory of plain MV3 files, zipped on request — and a page saying what to do
with the zip.

Because the instance serves its own build, the version it reports and the
version it hands out are the same file's, and skew between the app and the
extension is an edge case rather than the normal path.
"""

import io
import json
import os
import zipfile
from pathlib import Path
from string import Template
from typing import Any

from step_by_step_api.errors import ApiError

EXTENSION_DIR_VARIABLE = "EXTENSION_DIR"
"""Where the package is, when it is not where the repository keeps it.

The backend's image carries the extension at a path of its own, and a
deployment that builds the two separately points this at whichever build it
means to pair with.
"""

REPOSITORY_PACKAGE_DIR = Path(__file__).parents[4] / "extension" / "src"
"""`apps/extension/src` — the directory Chrome loads, and the zip's contents."""

MINIMUM_SUPPORTED_VERSION = "0.1.0"
"""The oldest extension this backend will record with.

It lives here rather than in the recording routes because two readers need the
same number: the version endpoint the app's banner reads, and the refusal a
recording session gives an extension that is too old.
"""


def package_dir() -> Path:
    """The directory the paired build is in."""
    return Path(os.environ.get(EXTENSION_DIR_VARIABLE) or REPOSITORY_PACKAGE_DIR)


def manifest() -> dict[str, Any]:
    """The build's own manifest, or a refusal naming what is missing.

    An instance without its extension is still an instance: people sign in,
    read Runs, and edit Workflows. So this is a 503 on the routes that need the
    package rather than a failure at boot — what is unavailable is the
    download, not the instance.
    """
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
    """The version of the build this instance serves."""
    return str(manifest()["version"])


def archive() -> bytes:
    """The build as a zip whose root is the folder Chrome is pointed at.

    The manifest has to sit at the top of the archive: the install sequence is
    to unzip and then load the unpacked folder, and a folder inside a folder is
    the one mistake that sequence invites.
    """
    root = package_dir()
    current_version()
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as building:
        for file in sorted(path for path in root.rglob("*") if path.is_file()):
            building.write(file, file.relative_to(root).as_posix())
    return buffer.getvalue()


INSTALL_PAGE_TEMPLATE = Path(__file__).parent / "install.html"
"""The install sequence, beside the module that serves it rather than in it."""


def install_page(current: str) -> str:
    """The install page, told which build it is describing."""
    written = Template(INSTALL_PAGE_TEMPLATE.read_text())
    return written.substitute(version=current, chrome=minimum_chrome_version())


def minimum_chrome_version() -> str:
    """The Chrome the build itself declares it needs."""
    return str(manifest().get("minimum_chrome_version", ""))
