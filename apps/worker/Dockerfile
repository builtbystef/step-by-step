# The Worker image: a Python process, and the desktop a headed browser needs.
#
# Built from the repository root, because the uv workspace resolves from the
# root pyproject.toml and uv.lock, and packages/core ships inside the image.
#
#   docker compose build worker
#
# The base is pinned to the uv the root pyproject.toml requires: the image has
# to run the same uv as CI and the developer's shell, or `uv sync` refuses.
FROM ghcr.io/astral-sh/uv:0.12.3-python3.14-trixie-slim

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PROJECT_ENVIRONMENT=/opt/venv \
    PLAYWRIGHT_BROWSERS_PATH=/opt/playwright \
    PYTHONUNBUFFERED=1

# The desktop: a display to draw on (xvfb), a VNC server to stream it
# (x11vnc), a window manager so the browser's own dialogs and popups behave
# (openbox), and xdpyinfo so the Worker can prove the display is open.
#
# Openbox rather than fluxbox: it manages windows and nothing else. Fluxbox
# insists on setting a root wallpaper, and with no wallpaper setter installed
# it parks an error dialog on the display — a window that would sit in every
# VNC frame and every screenshot Artifact for the life of the container.
RUN apt-get update \
 && apt-get install -y --no-install-recommends xvfb x11vnc openbox x11-utils \
 && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Dependencies first, from the manifests alone, so that editing source does not
# re-resolve or re-download anything. Every workspace member's manifest has to
# be here, because uv.lock covers the whole workspace and is validated against
# all of them — even the ones whose source this image does not carry.
COPY pyproject.toml uv.lock ./
COPY packages/core/pyproject.toml packages/core/
COPY apps/api/pyproject.toml apps/api/
COPY apps/worker/pyproject.toml apps/worker/
RUN uv sync --locked --package step-by-step-worker --no-dev --no-install-workspace

# Chromium, headed. --with-deps pulls the system libraries it needs.
RUN uv run --no-sync playwright install --with-deps chromium

COPY packages/core packages/core
COPY apps/worker apps/worker
RUN uv sync --locked --package step-by-step-worker --no-dev

ENV PATH="/opt/venv/bin:${PATH}" \
    DISPLAY=:99 \
    VNC_PORT=5900 \
    SCREEN_GEOMETRY=1280x1024x24

ENTRYPOINT ["/app/apps/worker/entrypoint.sh"]
