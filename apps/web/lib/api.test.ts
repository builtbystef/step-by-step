import { client, getCurrentAccount, getInstance } from "@step-by-step/api-client";
import { afterEach, describe, expect, it } from "vitest";

import { installUnauthorizedRedirect } from "./api";

/**
 * The one rule the wrapper owns: a 401 is not an error a screen renders, it is
 * a visitor who has no session, and the gate says where that puts them.
 *
 * The seam is the shared client every generated call already goes through, so
 * these tests answer a real generated function with a real status code.
 */

function answering(status: number, body: unknown = {}): typeof fetch {
  return () =>
    Promise.resolve(
      new Response(JSON.stringify(body), {
        status,
        headers: { "Content-Type": "application/json" },
      }),
    );
}

/** An instance that answers every call with `status`, and a log of where it sent us. */
function instanceAnswering(status: number): { went: string[] } {
  client.setConfig({ baseUrl: "http://api.test", fetch: answering(status) });
  return { went: [] };
}

let stop: (() => void) | undefined;

afterEach(() => {
  stop?.();
  stop = undefined;
  client.setConfig({ baseUrl: "", fetch: undefined });
});

describe("the fetch wrapper", () => {
  it("turns a 401 into the sign-in redirect, carrying where the visitor was", async () => {
    const { went } = instanceAnswering(401);
    stop = installUnauthorizedRedirect(
      (to) => went.push(to),
      () => "/runs?status=failed",
    );

    await getCurrentAccount();

    expect(went).toEqual(["/signin?next=/runs%3Fstatus%3Dfailed"]);
  });

  it("leaves the sign-in screen alone, where asking who you are answers 401", async () => {
    const { went } = instanceAnswering(401);
    stop = installUnauthorizedRedirect(
      (to) => went.push(to),
      () => "/signin?next=/runs",
    );

    await getCurrentAccount();

    expect(went).toEqual([]);
  });

  it("says nothing about an answer that is not a 401", async () => {
    const { went } = instanceAnswering(403);
    stop = installUnauthorizedRedirect(
      (to) => went.push(to),
      () => "/runs",
    );

    await getCurrentAccount();

    expect(went).toEqual([]);
  });

  it("covers every generated call, because they share one client", async () => {
    const { went } = instanceAnswering(401);
    stop = installUnauthorizedRedirect(
      (to) => went.push(to),
      () => "/runs",
    );

    await getInstance();

    expect(went).toEqual(["/signin?next=/runs"]);
  });

  it("stops when it is uninstalled, so a second install never doubles it", async () => {
    const { went } = instanceAnswering(401);
    installUnauthorizedRedirect(
      (to) => went.push(to),
      () => "/runs",
    )();

    await getCurrentAccount();

    expect(went).toEqual([]);
  });
});
