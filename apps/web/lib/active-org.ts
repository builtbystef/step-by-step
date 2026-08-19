import type { Account, OrganizationMembership } from "@step-by-step/api-client";

/**
 * Which Organization the app is acting in.
 *
 * Every org-scoped call carries it in the `X-Organization` header, so this is
 * the one choice that changes what every list on every screen shows. It is
 * resolved rather than stored: what this browser remembered is a preference,
 * and the identity is what says whether it is still a Membership at all — an
 * Organization somebody was removed from must not keep scoping their app.
 */

/** Where the choice lives across reloads. */
export const ACTIVE_ORGANIZATION_KEY = "step-by-step:active-organization";

/**
 * The Membership this browser is acting through: the one it remembered, the
 * first one otherwise, and none when there is nothing to act through.
 *
 * The first is a real answer rather than a placeholder — an account has at
 * least one Organization from the moment it exists, and somebody who never
 * opened the switcher is acting in it.
 */
export function activeOrganization(
  me: Account | null,
  remembered: string | null,
): OrganizationMembership | null {
  const orgs = me?.orgs ?? [];
  return orgs.find((org) => org.id === remembered) ?? orgs[0] ?? null;
}

/**
 * Whether the user menu offers a choice.
 *
 * With one Organization there is nothing to switch to, and a menu of one is a
 * question with a single answer: the name alone is the whole fact.
 */
export function offersASwitcher(me: Account | null): boolean {
  return (me?.orgs.length ?? 0) > 1;
}

/** The choice this browser made last, if it made one. */
export function rememberedOrganization(
  browser: Storage | undefined = localStorageOf(),
): string | null {
  return browser?.getItem(ACTIVE_ORGANIZATION_KEY) ?? null;
}

/**
 * Remember a choice, or give one up.
 *
 * Giving it up is what a `403 not_a_member` leaves behind: the Membership the
 * choice named is gone, and the next resolution has to start from the identity
 * rather than from a preference that no longer describes anything.
 */
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

/** This browser's memory, and nothing where there is no browser. */
function localStorageOf(): Storage | undefined {
  return typeof window === "undefined" ? undefined : window.localStorage;
}

/**
 * The choice as the app holds it, and the way to change it.
 *
 * Two things read it and neither owns it: the fetch wrapper, which stamps it
 * on every call, and the shell, which renders the name and the switcher. So it
 * lives here — one value, one way to change it, and whoever is watching hears.
 */

const WATCHERS = new Set<() => void>();

/** The Organization this browser has chosen, if it has chosen one. */
export function organizationChoice(browser: Storage | undefined = localStorageOf()): string | null {
  return rememberedOrganization(browser);
}

/**
 * Choose an Organization, or give the choice up.
 *
 * Everything the app has read was read as somebody acting in the old one, so
 * whoever is watching re-reads it: that is what "switching re-scopes the app"
 * means, and it is why this is one call rather than a write and a refresh.
 */
export function chooseOrganization(
  orgId: string | null,
  browser: Storage | undefined = localStorageOf(),
): void {
  rememberOrganization(orgId, browser);
  for (const watcher of [...WATCHERS]) {
    watcher();
  }
}

/** Hear about a choice being made, until the answer is called. */
export function watchOrganizationChoice(watcher: () => void): () => void {
  WATCHERS.add(watcher);
  return () => {
    WATCHERS.delete(watcher);
  };
}
