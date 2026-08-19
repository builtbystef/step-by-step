## Checks

One command vocabulary covers both languages: root pnpm scripts fan out through Vite+ (`vp`) to every workspace package (TypeScript directly, Python via ruff/ty/pytest under `uv run`). One failing package fails the command.

- Format: `pnpm check` (fix with `pnpm check:fix`)
- Lint: `pnpm check` (fix with `pnpm check:fix`)
- Typecheck: `pnpm check`
- Test: `pnpm test`

### Services

`docker compose up -d` starts the stack: Postgres, Redis, Garage, the backend, and a Worker. Copy `.env.example` to `.env` and load it — `set -a; source .env; set +a` — so the service URLs are in the environment; nothing reads a connection URL from anywhere else. Then `pnpm --filter api run migrate` applies the migrations.

Host ports are shifted off the defaults (Postgres 5433, Redis 6380, Garage 3910, the containerised backend 8001) because another project on the same machine holds 5432, 6379, 3900, and 8000. The Workers publish nothing at all — their VNC servers must stay on the compose network.

- Integration test tier: `pnpm test:integration` (needs the stack up and `.env` loaded)
- Browser test tier: `pnpm test:browser` (needs Playwright's Chromium: `uv run playwright install chromium`)
- Rebuild the images after changing a Dockerfile or a Python dependency: `docker compose build api worker`

`pnpm test` is the fast tier and stays green with no services and no browser installed.

`pnpm check` deliberately runs format + lint + typecheck as one pass. After changing an endpoint, `pnpm build` regenerates the OpenAPI schema and typed client — commit them (CI fails on drift). `pnpm run ci` is check + test + build.

## Project docs & tracker

### Domain glossary

`docs/GLOSSARY.md` — the project's terms. Use its vocabulary in code, tests, specs, and issues. The format rules are at the top of the file.

### Coding standards

`docs/CODING_STANDARDS.md` — the conventions beyond the linter. Reviews check diffs against it.

### Architecture & decisions

`docs/ARCHITECTURE.md` — the modules and the seams. `docs/adr/` — decisions already made (the format is in `docs/adr/README.md`). Do not debate them again.

### Issue tracker

`docs/TRACKER.md` — how to use this project's issue tracker.
