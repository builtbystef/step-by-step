import type { Account, Role } from "@step-by-step/api-client";

/**
 * The route gate: one pure function that decides, from the current identity
 * and the current path, whether a screen renders or where the visitor goes.
 *
 * It is pure on purpose. An expired session then costs one redirect rather
 * than a shell full of 401s with dead nav, and the whole guard is a table a
 * test can read back without a browser.
 */

/** Who the visitor is; `null` when there is no session. */
export type Identity = Account | null;

/** Render this screen, or send the visitor there instead. */
export type Gate = { kind: "render" } | { kind: "redirect"; to: string };

/** The one route that lives outside the shell. */
export const SIGN_IN_PATH = "/signin";

/** Where a signed-in visitor lands when nothing else claims them. */
export const HOME_PATH = "/workflows";

/** The panel any visitor may open, and so the fallback for a refused section. */
const ACCOUNT_PATH = "/settings/account";

/** Owners and admins manage Invitations; a member never sees the section. */
const INVITATIONS_PATH = "/settings/organization/invitations";

/**
 * The whole table, in order:
 *
 * | no session, and the path is `/signin` | render                          |
 * | no session                            | `/signin?next=<path+search>`    |
 * | the path is `/signin`                 | the Workflows list              |
 * | Invitations, and the role is `member`  | the Account panel              |
 * | otherwise                             | render                          |
 *
 * The owner-only controls inside `/settings/organization` hide by role rather
 * than gating the route: a member still reads the general section.
 */
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

/**
 * Where a visitor goes once they have an identity: back to what they asked
 * for, or to the Workflows list.
 *
 * `next` arrives in a URL anyone can write, so it is honored only when it is
 * a path of this app — one leading slash, and not an auth route, which would
 * land someone back where they began.
 */
export function landingAfterSignIn(next: string | null | undefined): string {
  if (!next || !isOwnPath(next) || isAuthRoute(pathOf(next))) {
    return HOME_PATH;
  }
  return next;
}

/** `/signin`, carrying the path that was asked for. */
function signInPath(wanted: string): string {
  return `${SIGN_IN_PATH}?next=${encodeCarriedPath(wanted)}`;
}

/**
 * The carried path as a query value. `encodeURIComponent` covers the `?` and
 * `&` that would otherwise end it; its `%2F` is put back, because a slash is
 * legal in a query value and `next=/runs%3Fstatus%3Dfailed` is readable where
 * `next=%2Fruns%3Fstatus%3Dfailed` is not.
 */
function encodeCarriedPath(path: string): string {
  return encodeURIComponent(path).replaceAll("%2F", "/");
}

/**
 * A path of this app, rather than somewhere else wearing a path's clothes.
 * `//evil.example` and `/\evil.example` are both protocol-relative URLs.
 */
function isOwnPath(candidate: string): boolean {
  return candidate.startsWith("/") && !candidate.startsWith("//") && !candidate.startsWith("/\\");
}

/** The path alone, without the query a caller may have kept on it. */
function pathOf(pathname: string): string {
  const query = pathname.indexOf("?");
  return query === -1 ? pathname : pathname.slice(0, query);
}

function isAuthRoute(path: string): boolean {
  return path === SIGN_IN_PATH;
}
