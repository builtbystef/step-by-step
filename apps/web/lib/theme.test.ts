import { describe, expect, it } from "vitest";

import {
  applyTheme,
  chooseTheme,
  rememberedTheme,
  resolveTheme,
  THEME_BOOT_SCRIPT,
  THEME_KEY,
} from "./theme";

function fakeStorage(initial: Record<string, string> = {}): Storage {
  const items = new Map(Object.entries(initial));
  return {
    getItem: (key) => items.get(key) ?? null,
    setItem: (key, value) => {
      items.set(key, value);
    },
    removeItem: (key) => {
      items.delete(key);
    },
    clear: () => {
      items.clear();
    },
    key: (index) => [...items.keys()][index] ?? null,
    get length() {
      return items.size;
    },
  };
}

function fakeRoot() {
  const classes = new Set<string>();
  return {
    classes,
    classList: {
      toggle(name: string, force?: boolean): boolean {
        const on = force ?? !classes.has(name);
        if (on) {
          classes.add(name);
        } else {
          classes.delete(name);
        }
        return on;
      },
    },
  };
}

describe("the theme", () => {
  it("follows the system until a person picks one", () => {
    expect(resolveTheme("system", true)).toBe("dark");
    expect(resolveTheme("system", false)).toBe("light");
    expect(resolveTheme("dark", false)).toBe("dark");
    expect(resolveTheme("light", true)).toBe("light");
  });

  it("reads only a real choice back from storage", () => {
    expect(rememberedTheme(fakeStorage())).toBe("system");
    expect(rememberedTheme(fakeStorage({ [THEME_KEY]: "dark" }))).toBe("dark");
    expect(rememberedTheme(fakeStorage({ [THEME_KEY]: "sepia" }))).toBe("system");
    expect(rememberedTheme(undefined)).toBe("system");
  });

  it("wears the dark class only for the dark theme", () => {
    const root = fakeRoot();
    applyTheme("dark", root);
    expect(root.classes.has("dark")).toBe(true);
    applyTheme("light", root);
    expect(root.classes.has("dark")).toBe(false);
  });

  it("remembers a picked theme and forgets the system one", () => {
    const storage = fakeStorage();
    const root = fakeRoot();

    chooseTheme("dark", storage, root, false);
    expect(storage.getItem(THEME_KEY)).toBe("dark");
    expect(root.classes.has("dark")).toBe(true);

    chooseTheme("system", storage, root, false);
    expect(storage.getItem(THEME_KEY)).toBeNull();
    expect(root.classes.has("dark")).toBe(false);
  });

  it("boots from the same key and class the store uses", () => {
    expect(THEME_BOOT_SCRIPT).toContain(JSON.stringify(THEME_KEY));
    expect(THEME_BOOT_SCRIPT).toContain('classList.add("dark")');
    expect(THEME_BOOT_SCRIPT).toContain("prefers-color-scheme: dark");
  });
});
