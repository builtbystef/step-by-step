import { defineConfig } from "vite-plus";

export default defineConfig({
  staged: {
    "*": "vp check --fix",
    "*.py": ["uv run ruff format", "uv run ruff check --fix"],
  },
  fmt: {
    // Machine-written files keep their generators' formatting so the CI
    // contract job can diff regenerated output against what's committed.
    // .beaver issue files are managed by the beaver CLI, not formatted here.
    ignorePatterns: ["**/src/generated/**", "**/openapi.json", ".beaver/**"],
  },
  lint: {
    plugins: ["typescript"],
    options: {
      typeAware: true,
      typeCheck: true,
    },
    ignorePatterns: ["**/dist/**", "**/coverage/**", "**/.next/**", "**/src/generated/**"],
    overrides: [
      {
        // `plugins` in an override replaces the base list, so repeat it.
        files: ["**/*.test.ts", "**/*.spec.ts"],
        plugins: ["typescript", "vitest"],
      },
    ],
  },
  test: {
    passWithNoTests: true,
  },
  pack: {
    dts: true,
    sourcemap: true,
  },
  run: {
    cache: true,
  },
});
