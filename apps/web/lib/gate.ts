import type { Account, Role } from "@step-by-step/api-client";

export type Identity = Account | null;

export type Gate = { kind: "render" } | { kind: "redirect"; to: string };

export const SIGN_IN_PATH = "/signin";

export const HOME_PATH = "/workflows";

export const ACCOUNT_PATH = "/settings/account";

const INVITATIONS_PATH = "/settings/organization/invitations";

export function resolveGate(me: Identity, activeOrgRole: Role | null, pathname: string): Gate {
  const path = pathOf(pathname);

  if (me === null) {
    return isAuthRoute(path) ? { kind: "render" } : { kind: "redirect", to: signInPath(pathname) };
  }
  if (isAuthRoute(path)) {
    return { kind: "redirect", to: HOME_PATH };
  }
  if (path === INVITATIONS_PATH && activeOrgRole === "member") {
    return { kind: "redirect", to: ACCOUNT_PATH };
  }
  return { kind: "render" };
}

export function landingAfterSignIn(next: string | null | undefined): string {
  if (!next || !isOwnPath(next) || isAuthRoute(pathOf(next))) {
    return HOME_PATH;
  }
  return next;
}

function signInPath(wanted: string): string {
  return `${SIGN_IN_PATH}?next=${encodeCarriedPath(wanted)}`;
}

function encodeCarriedPath(path: string): string {
  return encodeURIComponent(path).replaceAll("%2F", "/");
}

function isOwnPath(candidate: string): boolean {
  return candidate.startsWith("/") && !candidate.startsWith("//") && !candidate.startsWith("/\\");
}

function pathOf(pathname: string): string {
  const query = pathname.indexOf("?");
  return query === -1 ? pathname : pathname.slice(0, query);
}

function isAuthRoute(path: string): boolean {
  return path === SIGN_IN_PATH;
}
