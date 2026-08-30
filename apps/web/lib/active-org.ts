import type { Account, OrganizationMembership } from "@step-by-step/api-client";

export const ACTIVE_ORGANIZATION_KEY = "step-by-step:active-organization";

export function activeOrganization(
  me: Account | null,
  remembered: string | null,
): OrganizationMembership | null {
  const orgs = me?.orgs ?? [];
  return orgs.find((org) => org.id === remembered) ?? orgs[0] ?? null;
}

export function offersASwitcher(me: Account | null): boolean {
  return (me?.orgs.length ?? 0) > 1;
}

export function rememberedOrganization(
  browser: Storage | undefined = localStorageOf(),
): string | null {
  return browser?.getItem(ACTIVE_ORGANIZATION_KEY) ?? null;
}

export function rememberOrganization(
  orgId: string | null,
  browser: Storage | undefined = localStorageOf(),
): void {
  if (!browser) {
    return;
  }
  if (orgId === null) {
    browser.removeItem(ACTIVE_ORGANIZATION_KEY);
  } else {
    browser.setItem(ACTIVE_ORGANIZATION_KEY, orgId);
  }
}

function localStorageOf(): Storage | undefined {
  return typeof window === "undefined" ? undefined : window.localStorage;
}

const WATCHERS = new Set<() => void>();

export function organizationChoice(browser: Storage | undefined = localStorageOf()): string | null {
  return rememberedOrganization(browser);
}

export function chooseOrganization(
  orgId: string | null,
  browser: Storage | undefined = localStorageOf(),
): void {
  rememberOrganization(orgId, browser);
  for (const watcher of [...WATCHERS]) {
    watcher();
  }
}

export function watchOrganizationChoice(watcher: () => void): () => void {
  WATCHERS.add(watcher);
  return () => {
    WATCHERS.delete(watcher);
  };
}
