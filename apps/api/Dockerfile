# The backend image.
#
# Built from the repository root, because the uv workspace resolves from the
# root pyproject.toml and uv.lock, and packages/core ships inside the image.
#
#   docker compose build api
#
# The base is pinned to the uv the root pyproject.toml requires: the image has
# to run the same uv as CI and the developer's shell, or `uv sync` refuses.
FROM ghcr.io/astral-sh/uv:0.12.3-python3.14-trixie-slim

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PROJECT_ENVIRONMENT=/opt/venv \
    PYTHONUNBUFFERED=1

WORKDIR /app

# Registrable domains are Auth State's keys. libpsl supplies the maintained
# public-suffix list; string splitting cannot distinguish co.uk from github.io.
RUN apt-get update \
    && apt-get install --yes --no-install-recommends libpsl5 \
    && rm -rf /var/lib/apt/lists/*

# Dependencies first, from the manifests alone, so that editing source does not
# re-resolve or re-download anything. Every workspace member's manifest has to
# be here, because uv.lock covers the whole workspace and is validated against
# all of them — even the ones whose source this image does not carry.
COPY pyproject.toml uv.lock ./
COPY packages/core/pyproject.toml packages/core/
COPY apps/api/pyproject.toml apps/api/
COPY apps/worker/pyproject.toml apps/worker/
RUN uv sync --locked --package step-by-step-api --no-dev --no-install-workspace

COPY packages/core packages/core
COPY apps/api apps/api
RUN uv sync --locked --package step-by-step-api --no-dev

# The extension the backend serves as its own paired build. It is plain MV3
# files with no build step, so the source directory is the artifact; the
# variable is set rather than left to the default because the default is a
# path relative to this module's source, which an image need not keep.
COPY apps/extension/src apps/extension/src
ENV EXTENSION_DIR=/app/apps/extension/src

ENV PATH="/opt/venv/bin:${PATH}"
EXPOSE 8000
CMD ["uvicorn", "step_by_step_api.main:app", "--host", "0.0.0.0", "--port", "8000"]
