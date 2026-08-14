Step by Step records what a user does in the browser as an editable Workflow, and replays it — on demand, on a schedule, or over a list of inputs. The README carries the product summary; `docs/GLOSSARY.md` carries the vocabulary. Use both.

## Checks

One command vocabulary covers both languages. Root pnpm scripts fan out through Vite+ (`vp`) to every workspace package — TypeScript via `vp check`/`vp test`, Python via each package's `check`/`test` scripts (ruff, ty, pytest through `uv run`). One failing package fails the command.

- Format: `pnpm check` (fix with `pnpm check:fix`)
- Lint: `pnpm check` (fix with `pnpm check:fix`)
- Typecheck: `pnpm check`
- Test: `pnpm test`

`pnpm check` deliberately runs format + lint + typecheck as one pass; there are no separate per-check commands. `pnpm build` regenerates the OpenAPI schema and the typed client from it — run it after changing an endpoint, and commit the regenerated files (CI fails on drift). `pnpm run ci` is check + test + build (bare `pnpm ci` is pnpm's clean-install).

Run the app locally: `pnpm dev` (FastAPI on :8000, Next.js on :3000). One-time setup after cloning: `pnpm install`, `uv sync`, then `vp config` to activate the pre-commit hook.

While you work, run the check that your change touches; before you end a session that changed code, run all of the checks, and each one must pass.

## Project docs & tracker

### Domain glossary

`docs/GLOSSARY.md` — the project's terms. Use its vocabulary in code, tests, specs, and issues. The format rules are at the top of the file.

### Coding standards

`docs/CODING_STANDARDS.md` — the conventions beyond the linter. Reviews check diffs against it.

### Architecture & decisions

`docs/ARCHITECTURE.md` — the modules and the seams. `docs/adr/` — decisions already made (the format is in `docs/adr/README.md`). Do not debate them again.

### Issue tracker

`docs/TRACKER.md` — how to use this project's issue tracker.
