export const THEME_KEY = "step-by-step:theme";

/** What a person picks: a theme, or to follow their system. */
export type ThemeChoice = "system" | "light" | "dark";

/** What the page actually wears. */
export type Theme = "light" | "dark";

export const THEME_CHOICES: readonly { value: ThemeChoice; label: string }[] = [
  { value: "system", label: "Match the system" },
  { value: "light", label: "Light" },
  { value: "dark", label: "Dark" },
];

const DARK_QUERY = "(prefers-color-scheme: dark)";
const DARK_CLASS = "dark";

export function isThemeChoice(value: unknown): value is ThemeChoice {
  return value === "system" || value === "light" || value === "dark";
}

export function resolveTheme(choice: ThemeChoice, systemPrefersDark: boolean): Theme {
  if (choice === "system") {
    return systemPrefersDark ? "dark" : "light";
  }
  return choice;
}

export function rememberedTheme(browser: Storage | undefined = localStorageOf()): ThemeChoice {
  const stored = browser?.getItem(THEME_KEY);
  return isThemeChoice(stored) ? stored : "system";
}

export function rememberTheme(
  choice: ThemeChoice,
  browser: Storage | undefined = localStorageOf(),
): void {
  if (!browser) {
    return;
  }
  if (choice === "system") {
    browser.removeItem(THEME_KEY);
  } else {
    browser.setItem(THEME_KEY, choice);
  }
}

type Root = { classList: Pick<DOMTokenList, "toggle"> };

export function applyTheme(theme: Theme, root: Root | undefined = rootOf()): void {
  root?.classList.toggle(DARK_CLASS, theme === "dark");
}

/**
 * Runs before the first paint, from the document head, so a dark page never
 * flashes light. It repeats the rules above on purpose: nothing imported can
 * run that early.
 */
export const THEME_BOOT_SCRIPT = [
  "(function(){try{",
  `var c=localStorage.getItem(${JSON.stringify(THEME_KEY)});`,
  `if(c==="dark"||(c!=="light"&&matchMedia(${JSON.stringify(DARK_QUERY)}).matches))`,
  `document.documentElement.classList.add(${JSON.stringify(DARK_CLASS)});`,
  "}catch(e){}})()",
].join("");

const WATCHERS = new Set<() => void>();

function notify(): void {
  for (const watcher of [...WATCHERS]) {
    watcher();
  }
}

export function chooseTheme(
  choice: ThemeChoice,
  browser: Storage | undefined = localStorageOf(),
  root: Root | undefined = rootOf(),
  systemPrefersDark: boolean = systemPrefersDarkNow(),
): void {
  rememberTheme(choice, browser);
  applyTheme(resolveTheme(choice, systemPrefersDark), root);
  notify();
}

/** Keeps the page in step with the system while the choice is "system", and with other tabs. */
export function followTheme(): () => void {
  const media = window.matchMedia(DARK_QUERY);
  const sync = () => {
    applyTheme(resolveTheme(rememberedTheme(), media.matches));
    notify();
  };
  const onStorage = (event: StorageEvent) => {
    if (event.key === null || event.key === THEME_KEY) {
      sync();
    }
  };

  sync();
  media.addEventListener("change", sync);
  window.addEventListener("storage", onStorage);

  return () => {
    media.removeEventListener("change", sync);
    window.removeEventListener("storage", onStorage);
  };
}

export function watchTheme(watcher: () => void): () => void {
  WATCHERS.add(watcher);
  return () => {
    WATCHERS.delete(watcher);
  };
}

function localStorageOf(): Storage | undefined {
  return typeof window === "undefined" ? undefined : window.localStorage;
}

function rootOf(): Root | undefined {
  return typeof document === "undefined" ? undefined : document.documentElement;
}

function systemPrefersDarkNow(): boolean {
  return typeof window !== "undefined" && window.matchMedia(DARK_QUERY).matches;
}
