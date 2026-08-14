## Checks

One command vocabulary covers both languages: root pnpm scripts fan out through Vite+ (`vp`) to every workspace package (TypeScript directly, Python via ruff/ty/pytest under `uv run`). One failing package fails the command.

- Format: `pnpm check` (fix with `pnpm check:fix`)
- Lint: `pnpm check` (fix with `pnpm check:fix`)
- Typecheck: `pnpm check`
- Test: `pnpm test`

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
