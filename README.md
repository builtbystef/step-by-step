<p align="center">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="docs/assets/logo-full-dark.svg">
    <img src="docs/assets/logo-full.svg" alt="Step by Step" width="380">
  </picture>
</p>

<p align="center">
  <b>An open-source, self-hosted browser automation tool.</b><br>
  Record semantic Workflows with a Chrome extension, run them on isolated Workers,<br>
  and take over the browser yourself when a step needs a person.
</p>

<p align="center">
  <a href="https://github.com/builtbystef/step-by-step/actions/workflows/ci.yml"><img src="https://github.com/builtbystef/step-by-step/actions/workflows/ci.yml/badge.svg" alt="CI"></a>
  <a href="LICENSE"><img src="https://img.shields.io/badge/license-MIT-blue.svg" alt="License: MIT"></a>
</p>

<p align="center">
  <a href="#features">Features</a> ·
  <a href="#screenshots">Screenshots</a> ·
  <a href="#how-it-works">How it works</a> ·
  <a href="#quick-start">Quick start</a> ·
  <a href="#development">Development</a> ·
  <a href="#configuration">Configuration</a> ·
  <a href="#project-docs">Docs</a>
</p>

---

Step by Step is an open-source, self-hosted browser automation tool. Its Chrome extension records semantic actions such as navigation, clicks, typing, selection, downloads, extraction, waits, and human takeover points. The web app lets you edit and version those Workflows, provide Variables, and inspect every Run.

When automation reaches something that requires a person, such as MFA, a CAPTCHA, or an unexpected page, you can take control of the Worker's browser and then hand it back. Screenshots, downloads, traces, logs, and extracted data are retained with the Run.

> [!WARNING]
> Step by Step is under active development and has not reached a stable release. APIs, configuration, and stored data may change without a migration path.

## Features

- **Browser recording** with a Chrome MV3 extension
- **Editable, versioned Workflows** made from semantic Steps rather than generated scripts
- **Reusable Variables and encrypted Secrets**, including per-member Personal Overrides
- **Saved browser Auth State** for authenticated sites
- **Manual, scheduled, and Batch Runs**
- **Human takeover** through a live view of the Worker's browser
- **Run history** with Step Results, logs, screenshots, downloads, traces, and extracted output
- **Selector fallback and drift detection** when pages change
- **Organizations and passwordless email sign-in**
- **Self-hosted storage and execution** using PostgreSQL, Redis, Garage, and isolated Playwright Workers

## Screenshots

Light and dark captures of every screen, including Schedules, Secrets, saved logins, the recorder, and settings, are in [`docs/screenshots`](docs/screenshots).

### Workflows

The home list: each Workflow shows its latest Run, any Schedule, and whether the Draft is in sync with a Version.

<a href="docs/screenshots/v2/light/02-workflows.png">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="docs/screenshots/v2/dark/02-workflows.png">
    <img alt="Workflows list with recent Run status, Schedules, and publish state" src="docs/screenshots/v2/light/02-workflows.png">
  </picture>
</a>

### Editor

A Draft of semantic Steps. Values can reference Variables; a pause-for-takeover Step hands the Worker's browser to a person.

<a href="docs/screenshots/v2/light/15-editor-human-review.png">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="docs/screenshots/v2/dark/15-editor-human-review.png">
    <img alt="Workflow editor showing a catering order Draft with Variables and a pause-for-takeover Step" src="docs/screenshots/v2/light/15-editor-human-review.png">
  </picture>
</a>

### Human takeover

When a Run waits, you take control of the Worker's browser and hand it back. The timeline records waiting, control, and verification.

<a href="docs/screenshots/v2/light/29-run-human-review.png">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="docs/screenshots/v2/dark/29-run-human-review.png">
    <img alt="Succeeded Run whose timeline shows waiting for a person, control, and handing the browser back" src="docs/screenshots/v2/light/29-run-human-review.png">
  </picture>
</a>

### Run history

Each Step Result keeps the selector that matched, extracted records, screenshots, and drift against the recorded candidates.

<a href="docs/screenshots/v2/light/50-run-expanded-records.png">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="docs/screenshots/v2/dark/50-run-expanded-records.png">
    <img alt="Expanded Step Result with selector drift, a screenshot, and extracted quote records" src="docs/screenshots/v2/light/50-run-expanded-records.png">
  </picture>
</a>

### Selector drift

When a page changes, the Run shows which candidates died and keeps a screenshot of the failure.

<a href="docs/screenshots/v2/light/54-run-failed-step-and-screenshot.png">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="docs/screenshots/v2/dark/54-run-failed-step-and-screenshot.png">
    <img alt="Failed Run with selector failure details, drift, and a screenshot of the page" src="docs/screenshots/v2/light/54-run-failed-step-and-screenshot.png">
  </picture>
</a>

### Batches

A Batch runs one Workflow across a list of input rows, one at a time, and lets you re-run a failed row.

<a href="docs/screenshots/v2/light/22-batch-books.png">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="docs/screenshots/v2/dark/22-batch-books.png">
    <img alt="Batch of book-catalogue rows with succeeded, skipped, and failed status" src="docs/screenshots/v2/light/22-batch-books.png">
  </picture>
</a>

## How it works

```mermaid
flowchart LR
    Extension[Chrome extension] -->|records Steps| API[FastAPI API]
    Web[Next.js web app] -->|edits and starts Workflows| API
    API --> Postgres[(PostgreSQL)]
    API --> Redis[(Redis)]
    Redis --> Worker[Playwright Worker]
    Worker --> Postgres
    Worker --> Garage[(Garage / S3)]
    Web -->|live view and takeover| API
    API --> Worker
```

A Workflow has one mutable **Draft**. Publishing the Draft creates an immutable **Version**, and Runs execute a Version. PostgreSQL is the source of truth; Redis carries dispatch and live-event hints; Garage stores Artifacts. Each Worker runs at most one browser at a time.

See [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) for the full system design and [`docs/GLOSSARY.md`](docs/GLOSSARY.md) for the project's domain language.

## Quick start

The quickest development setup runs the API, Worker, and backing services in Docker, with the web app on the host.

### Prerequisites

- Docker with Compose
- Node.js 24 or newer (the repository pins 24.18)
- pnpm 11.17 (the repository pins it through `packageManager`)
- Google Chrome or Chromium 118 or newer

### Run the project

```bash
git clone https://github.com/builtbystef/step-by-step.git
cd step-by-step

cp .env.example .env
pnpm install --frozen-lockfile

docker compose up -d --build
docker compose exec -w /app/apps/api api alembic upgrade head

API_URL=http://localhost:8001 pnpm --filter web dev
```

Open [http://localhost:3000](http://localhost:3000).

The default development mailer writes Sign-in Codes to the API log instead of sending email. Follow the log while signing in:

```bash
docker compose logs -f api
```

After signing in, open [http://localhost:3000/extension](http://localhost:3000/extension) and follow the instructions to load the recorder in Chrome.

Stop the stack with:

```bash
docker compose down
```

Data is retained in Docker volumes. To remove all local data as well, use `docker compose down -v`.

> [!IMPORTANT]
> The Compose defaults are for local development. They contain known credentials, use the console mailer, and do not configure TLS. Do not expose this setup to the internet unchanged.

## Development

For work across both the TypeScript and Python packages, install the complete toolchain:

- Node.js version from [`.node-version`](.node-version)
- Python version from [`.python-version`](.python-version)
- pnpm version from [`package.json`](package.json)
- uv version from [`pyproject.toml`](pyproject.toml)

```bash
pnpm install --frozen-lockfile
uv sync --locked --all-packages
cp .env.example .env
set -a; source .env; set +a

docker compose up -d
pnpm --filter api run migrate
pnpm dev
```

`pnpm dev` starts FastAPI on port 8000 and Next.js on port 3000. The Compose stack also exposes its containerized API on port 8001, PostgreSQL on 5433, Redis on 6380, and Garage's S3 API on 3910.

### Checks

```bash
pnpm check              # format, lint, and typecheck every package
pnpm test               # fast tests; no services or browser required
pnpm build              # build and regenerate the API contract
pnpm run ci              # check, test, and build
```

Additional test tiers:

```bash
pnpm test:integration   # requires the Compose stack and .env loaded
pnpm test:browser       # requires: uv run playwright install chromium
```

When an API endpoint changes, run `pnpm build` and commit the regenerated OpenAPI schema and typed client.

## Repository layout

```text
apps/
  api/          FastAPI backend and Alembic migrations
  extension/    Chrome MV3 recording extension
  web/          Next.js web application
  worker/       Playwright execution Worker
packages/
  api-client/   Generated TypeScript API client
  core/         Shared Python contracts and infrastructure seams
compose/        Service configuration
docs/           Architecture, glossary, standards, ADRs, and screenshots
```

## Project docs

- [`AGENTS.md`](AGENTS.md): repository commands and agent instructions
- [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md): system parts and their boundaries
- [`docs/GLOSSARY.md`](docs/GLOSSARY.md): shared product terms
- [`docs/CODING_STANDARDS.md`](docs/CODING_STANDARDS.md): rules not enforced by formatters or linters
- [`docs/adr/`](docs/adr/): decisions that are costly to reverse
- [`docs/TRACKER.md`](docs/TRACKER.md): Beaver Backlog commands used by this project
- [`docs/screenshots`](docs/screenshots): light and dark captures of the web app

## Configuration

Copy [`.env.example`](.env.example) for application settings, development service URLs, and documented defaults. Important production-facing settings include:

- `STEPBYSTEP_MASTER_KEY`: encrypts Secrets and Auth State; losing it makes those values unrecoverable
- `INTERNAL_TOKEN`: authenticates Worker-to-API requests
- `VNC_CONTROL_PASSWORD` and `VNC_VIEW_PASSWORD`: protect Worker browser access
- `SIGNUP_MODE`: use `invite_only` for a private instance
- `MAILER`: `console`, `smtp`, or `resend`
- `S3_*`: Artifact storage credentials and endpoints

Before operating an internet-facing instance, replace every development credential, configure real email delivery, put the application behind TLS, and arrange backups for PostgreSQL and Artifact storage.

## License

Step by Step is available under the [MIT License](LICENSE).
