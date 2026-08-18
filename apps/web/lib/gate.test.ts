import type { Account } from "@step-by-step/api-client";
import { describe, expect, it } from "vitest";

import { landingAfterSignIn, resolveGate } from "./gate";

/**
 * The guard's whole table, exercised directly: no browser, no DOM, no router.
 * Every row below is a worked example from the spec.
 */

const SIGNED_IN: Account = {
  id: "3f0d7c1e-0000-4000-8000-000000000001",
  email: "ada@example.com",
  display_name: "Ada",
  orgs: [{ id: "3f0d7c1e-0000-4000-8000-000000000002", name: "ada", role: "member" }],
};

describe("resolveGate", () => {
  it("sends a signed-out visitor to sign-in, carrying where they were going", () => {
    expect(resolveGate(null, null, "/runs")).toEqual({
      kind: "redirect",
      to: "/signin?next=/runs",
    });
  });

  it("encodes the query of the path it carries, so it round-trips", () => {
    const gate = resolveGate(null, null, "/runs?status=failed");

    expect(gate).toEqual({ kind: "redirect", to: "/signin?next=/runs%3Fstatus%3Dfailed" });

    const carried = new URL(`https://example.test${gate.kind === "redirect" ? gate.to : ""}`);
    expect(carried.searchParams.get("next")).toBe("/runs?status=failed");
  });

  it("renders sign-in for a signed-out visitor, rather than redirecting to itself", () => {
    expect(resolveGate(null, null, "/signin")).toEqual({ kind: "render" });
  });

  it("sends a signed-in visitor off the sign-in screen", () => {
    expect(resolveGate(SIGNED_IN, "member", "/signin")).toEqual({
      kind: "redirect",
      to: "/workflows",
    });
  });

  it("keeps a member out of Invitations, which owners and admins manage", () => {
    expect(resolveGate(SIGNED_IN, "member", "/settings/organization/invitations")).toEqual({
      kind: "redirect",
      to: "/settings/account",
    });
  });

  it("lets an admin into Invitations", () => {
    expect(resolveGate(SIGNED_IN, "admin", "/settings/organization/invitations")).toEqual({
      kind: "render",
    });
  });

  it("lets an owner into the Organization's general section", () => {
    expect(resolveGate(SIGNED_IN, "owner", "/settings/organization")).toEqual({ kind: "render" });
  });

  it("renders every other path for a signed-in visitor", () => {
    expect(resolveGate(SIGNED_IN, "member", "/runs?status=failed")).toEqual({ kind: "render" });
  });
});

describe("landingAfterSignIn", () => {
  it("honors a path of this app", () => {
    expect(landingAfterSignIn("/runs?status=failed")).toBe("/runs?status=failed");
  });

  it("refuses an absolute URL elsewhere", () => {
    expect(landingAfterSignIn("https://evil.example/x")).toBe("/workflows");
  });

  it("refuses a protocol-relative URL, which starts with two slashes", () => {
    expect(landingAfterSignIn("//evil.example/x")).toBe("/workflows");
    expect(landingAfterSignIn("/\\evil.example/x")).toBe("/workflows");
  });

  it("refuses an auth route, which would land the visitor back where they began", () => {
    expect(landingAfterSignIn("/signin")).toBe("/workflows");
    expect(landingAfterSignIn("/signin?next=/runs")).toBe("/workflows");
  });

  it("falls back to the Workflows list when nothing was carried", () => {
    expect(landingAfterSignIn(null)).toBe("/workflows");
    expect(landingAfterSignIn("")).toBe("/workflows");
  });
});
