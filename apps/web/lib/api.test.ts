import { client, getCurrentAccount, getInstance } from "@step-by-step/api-client";
import { afterEach, describe, expect, it } from "vitest";

import {
  installMembershipLapsed,
  installOrganizationHeader,
  installUnauthorizedRedirect,
} from "./api";

function answering(status: number, body: unknown = {}): typeof fetch {
  return () =>
    Promise.resolve(
      new Response(JSON.stringify(body), {
        status,
        headers: { "Content-Type": "application/json" },
      }),
    );
}

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

function recording(status: number, body: unknown = {}): { sent: Request[] } {
  const sent: Request[] = [];
  const keeping: typeof fetch = (asked) => {
    if (asked instanceof Request) {
      sent.push(asked);
    }
    return Promise.resolve(
      new Response(JSON.stringify(body), {
        status,
        headers: { "Content-Type": "application/json" },
      }),
    );
  };

  client.setConfig({ baseUrl: "http://api.test", fetch: keeping });
  return { sent };
}

describe("the active Organization's header", () => {
  it("rides on every call, because that is what scopes them", async () => {
    const { sent } = recording(200);
    stop = installOrganizationHeader(() => "org-acme");

    await getCurrentAccount();
    await getInstance();

    expect(sent.map((request) => request.headers.get("X-Organization"))).toEqual([
      "org-acme",
      "org-acme",
    ]);
  });

  it("is read at the call rather than captured, so switching takes effect at once", async () => {
    const { sent } = recording(200);
    let active = "org-acme";
    stop = installOrganizationHeader(() => active);

    await getCurrentAccount();
    active = "org-bolt";
    await getCurrentAccount();

    expect(sent.map((request) => request.headers.get("X-Organization"))).toEqual([
      "org-acme",
      "org-bolt",
    ]);
  });

  it("is absent when no Organization is active, rather than empty", async () => {
    const { sent } = recording(200);
    stop = installOrganizationHeader(() => null);

    await getCurrentAccount();

    expect(sent[0]?.headers.has("X-Organization")).toBe(false);
  });
});

describe("a Membership that ended mid-tab", () => {
  it("gives up the Organization the call named", async () => {
    recording(403, { code: "not_a_member", message: "you are not a member" });
    const lapsed: number[] = [];
    stop = installMembershipLapsed(() => lapsed.push(1));

    await getCurrentAccount();

    expect(lapsed).toEqual([1]);
  });

  it("leaves the answer readable, so the screen still reads its refusal", async () => {
    recording(403, { code: "not_a_member", message: "you are not a member" });
    stop = installMembershipLapsed(() => undefined);

    const { error } = await getCurrentAccount();

    expect(error).toEqual({ code: "not_a_member", message: "you are not a member" });
  });

  it("says nothing about a refusal that is about a role rather than a Membership", async () => {
    recording(403, { code: "not_an_admin", message: "only an owner or an admin may manage this" });
    const lapsed: number[] = [];
    stop = installMembershipLapsed(() => lapsed.push(1));

    await getCurrentAccount();

    expect(lapsed).toEqual([]);
  });

  it("says nothing about a refusal it cannot read", async () => {
    client.setConfig({
      baseUrl: "http://api.test",
      fetch: () => Promise.resolve(new Response("<html>gateway</html>", { status: 403 })),
    });
    const lapsed: number[] = [];
    stop = installMembershipLapsed(() => lapsed.push(1));

    await getCurrentAccount();

    expect(lapsed).toEqual([]);
  });
});
