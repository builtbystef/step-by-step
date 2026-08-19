import { client } from "@step-by-step/api-client";

import { resolveGate } from "./gate";

/** The header the backend reads the acting Organization from. */
const ORGANIZATION_HEADER = "X-Organization";

/**
 * The global fetch wrapper: the one place an answer from the API can move the
 * whole app.
 *
 * Every generated call goes through one shared client, so a rule installed
 * here covers all of them — there is no second path to the backend to keep in
 * step. Three rules live here, each installed on its own:
 *
 * - The active Organization's `X-Organization` header, stamped on the way out,
 *   because that header is what scopes an org-scoped route.
 * - A 401 is not an error a screen renders: it is a visitor with no session,
 *   which is a question the gate already answers.
 * - A `403 not_a_member` is a Membership that ended while this tab was open,
 *   and the choice that named it is given up rather than kept.
 *
 * A tab left open across a session expiry or a removal therefore recovers
 * instead of rendering a screenful of errors.
 */

/**
 * Install the 401 rule and answer with its uninstaller.
 *
 * `navigate` is the router's, and `here` is the path the visitor is on when an
 * answer arrives — read at that moment rather than captured, so a redirect
 * carries where they actually are.
 */
export function installUnauthorizedRedirect(
  navigate: (to: string) => void,
  here: () => string = currentPath,
): () => void {
  const installed = client.interceptors.response.use((response: Response) => {
    if (response.status === 401) {
      const gate = resolveGate(null, null, here());
      if (gate.kind === "redirect") {
        navigate(gate.to);
      }
    }
    return response;
  });

  return () => client.interceptors.response.eject(installed);
}

/** Where the visitor is, as the gate reads a path: the route and its query. */
function currentPath(): string {
  return `${window.location.pathname}${window.location.search}`;
}

/**
 * Stamp the active Organization on every call, and answer with its uninstaller.
 *
 * `activeOrganization` is called per request rather than captured: switching
 * Organization has to re-scope the very next call, and a value read once at
 * install time would keep scoping the app to where the visitor used to be.
 * Nothing is stamped when no Organization is active — the backend refuses an
 * absent header where it needs one, and an empty one would be a lie about it.
 */
export function installOrganizationHeader(activeOrganization: () => string | null): () => void {
  const installed = client.interceptors.request.use((request: Request) => {
    const active = activeOrganization();
    if (active !== null) {
      request.headers.set(ORGANIZATION_HEADER, active);
    }
    return request;
  });

  return () => client.interceptors.request.eject(installed);
}

/**
 * Install the lapsed-Membership rule and answer with its uninstaller.
 *
 * A `403 not_a_member` says the Organization this browser is acting in is one
 * the visitor is no longer in — removed from another tab, or ended by its
 * owner. The choice is given up and the app re-resolves from the identity,
 * which is what turns a tab full of refusals back into a working one.
 *
 * The answer is read from a clone: it is the screen's to consume, and a
 * wrapper that drank the body would leave the refusal unreadable.
 */
export function installMembershipLapsed(onLapsed: () => void): () => void {
  const installed = client.interceptors.response.use(async (response: Response) => {
    if (response.status === 403 && (await refusalCode(response)) === "not_a_member") {
      onLapsed();
    }
    return response;
  });

  return () => client.interceptors.response.eject(installed);
}

/** The `code` of a refusal, or nothing when the answer is not one at all. */
async function refusalCode(response: Response): Promise<string | undefined> {
  try {
    const body: unknown = await response.clone().json();
    return typeof body === "object" && body !== null && "code" in body
      ? String(body.code)
      : undefined;
  } catch {
    return undefined;
  }
}
