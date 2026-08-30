import { client } from "@step-by-step/api-client";
import { QueryClient } from "@tanstack/react-query";
import { afterEach, describe, expect, it } from "vitest";

import {
  IDENTITY_KEY,
  deleteAccountAndLeave,
  signOutAndLeave,
  signOutEverywhereAndLeave,
} from "./identity";

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

describe("signing out everywhere", () => {
  it("leaves this browser exactly where signing out here does", async () => {
    instanceAnswering(204);
    const cache = new QueryClient();
    cache.setQueryData(IDENTITY_KEY, { email: "ada@example.com" });
    const went: string[] = [];

    await signOutEverywhereAndLeave(cache, (to) => went.push(to));

    expect(cache.getQueryData(IDENTITY_KEY)).toBeUndefined();
    expect(went).toEqual(["/signin"]);
  });

  it("asks the instance to end every session and not just this one", async () => {
    const asked: string[] = [];
    client.setConfig({
      baseUrl: "http://api.test",
      fetch: (asking: URL | RequestInfo) => {
        asked.push(new URL(asking instanceof Request ? asking.url : asking.toString()).pathname);
        return Promise.resolve(new Response(null, { status: 204 }));
      },
    });

    await signOutEverywhereAndLeave(new QueryClient(), () => {});

    expect(asked).toEqual(["/api/auth/logout-all"]);
  });
});

describe("deleting the account", () => {
  it("leaves this browser where signing out does, holding nothing", async () => {
    instanceAnswering(204);
    const cache = new QueryClient();
    cache.setQueryData(IDENTITY_KEY, { email: "ada@example.com" });
    const went: string[] = [];

    await deleteAccountAndLeave(cache, (to) => went.push(to), "ada@example.com");

    expect(cache.getQueryData(IDENTITY_KEY)).toBeUndefined();
    expect(went).toEqual(["/signin"]);
  });

  it("keeps the visitor where they are when the instance refuses", async () => {
    client.setConfig({
      baseUrl: "http://api.test",
      fetch: () =>
        Promise.resolve(
          new Response(JSON.stringify({ code: "sole_owner", message: "" }), {
            status: 403,
            headers: { "Content-Type": "application/json" },
          }),
        ),
    });
    const cache = new QueryClient();
    cache.setQueryData(IDENTITY_KEY, { email: "ada@example.com" });
    const went: string[] = [];

    await expect(
      deleteAccountAndLeave(cache, (to) => went.push(to), "ada@example.com"),
    ).rejects.toMatchObject({ code: "sole_owner" });
    expect(cache.getQueryData(IDENTITY_KEY)).toEqual({ email: "ada@example.com" });
    expect(went).toEqual([]);
  });

  it("types the address the person entered, and not the one it holds", async () => {
    const sent: string[] = [];
    client.setConfig({
      baseUrl: "http://api.test",
      fetch: async (asking: URL | RequestInfo) => {
        sent.push(asking instanceof Request ? await asking.text() : "");
        return new Response(null, { status: 204 });
      },
    });

    await deleteAccountAndLeave(new QueryClient(), () => {}, "Ada@Example.com");

    expect(sent).toEqual([JSON.stringify({ email_confirmation: "Ada@Example.com" })]);
  });
});
