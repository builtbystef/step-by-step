# Step by Step

Record what you do in the browser, edit it, and replay it — on demand, on a schedule, or over a list of inputs.

You install a Chrome extension and perform a task on a website once. Step by Step records it as a **Workflow**: a named sequence of editable, semantic **Steps** (navigate, click, type, select, download, extract, wait, pause-for-takeover). You then edit that Workflow in the web app, declare the **Variables** it takes, and run it. When a site demands a human — a CAPTCHA, an MFA prompt — the Run pauses, you take control of its browser, and hand it back. Every Run keeps its screenshots, downloads, traces, and extracted data.

## Status

The stack has landed; the product areas are next. The six areas are specced, the decisions are recorded, and the monorepo is scaffolded — a Next.js/TypeScript frontend, a FastAPI/Python backend joined by a generated typed API client, with SQLAlchemy 2 + Alembic ready for the first table. See the roadmap (`.beaver/issues/idnzwf-*.md`) for what is settled and what is still open, and [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) for the layout.

The full shape: versioned Workflows in PostgreSQL, Redis-queued Runs on isolated Playwright Workers, and object storage for artifacts — one docker compose stack. Setup and commands are in [`AGENTS.md`](AGENTS.md): `pnpm install`, `uv sync`, then `pnpm dev`.

## Docs

| File                                                   | What it holds                                             |
| ------------------------------------------------------ | --------------------------------------------------------- |
| [`AGENTS.md`](AGENTS.md)                               | How to work in this repository; the check commands.       |
| [`docs/GLOSSARY.md`](docs/GLOSSARY.md)                 | The project's vocabulary. Code, specs, and issues use it. |
| [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md)         | The modules and the seams between them.                   |
| [`docs/CODING_STANDARDS.md`](docs/CODING_STANDARDS.md) | The conventions beyond the linter.                        |
| [`docs/adr/`](docs/adr/)                               | Decisions already made, and why.                          |
| [`docs/TRACKER.md`](docs/TRACKER.md)                   | How the issue tracker works here.                         |

## License

MIT — see [LICENSE](LICENSE).
