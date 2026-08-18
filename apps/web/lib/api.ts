import { client } from "@step-by-step/api-client";

import { resolveGate } from "./gate";

/**
 * The global fetch wrapper: the one place an answer from the API can move the
 * whole app.
 *
 * Every generated call goes through one shared client, so a rule installed
 * here covers all of them — there is no second path to the backend to keep in
 * step. Today it owns one rule: a 401 means the visitor has no session, which
 * is a question the gate already answers. A tab left open across a session
 * expiry therefore recovers with a redirect instead of rendering a screenful
 * of errors.
 *
 * The active Organization's `X-Organization` header belongs here too, and
 * lands with the shell, which is what knows which Organization is active.
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
