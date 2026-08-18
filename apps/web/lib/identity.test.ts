import { client } from "@step-by-step/api-client";
import { QueryClient } from "@tanstack/react-query";
import { afterEach, describe, expect, it } from "vitest";

import { IDENTITY_KEY, signOutAndLeave } from "./identity";

/**
 * Signing out is two things, and both have to happen: the session ends on the
 * server, and the identity this browser is holding goes with it. What is left
 * behind is a visitor on the sign-in screen with nothing to come back to.
 */

afterEach(() => {
  client.setConfig({ baseUrl: "", fetch: undefined });
});

function instanceAnswering(status: number): void {
  client.setConfig({
    baseUrl: "http://api.test",
    fetch: () => Promise.resolve(new Response(null, { status })),
  });
}

describe("signing out", () => {
  it("clears the identity and lands on sign-in with nothing carried", async () => {
    instanceAnswering(204);
    const cache = new QueryClient();
    cache.setQueryData(IDENTITY_KEY, { email: "ada@example.com" });
    const went: string[] = [];

    await signOutAndLeave(cache, (to) => went.push(to));

    expect(cache.getQueryData(IDENTITY_KEY)).toBeUndefined();
    expect(went).toEqual(["/signin"]);
  });

  it("lets go even when the session was already gone", async () => {
    instanceAnswering(401);
    const cache = new QueryClient();
    cache.setQueryData(IDENTITY_KEY, { email: "ada@example.com" });
    const went: string[] = [];

    await signOutAndLeave(cache, (to) => went.push(to));

    expect(cache.getQueryData(IDENTITY_KEY)).toBeUndefined();
    expect(went).toEqual(["/signin"]);
  });
});
