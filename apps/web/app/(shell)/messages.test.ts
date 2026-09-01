import type { OfferedMembership } from "@step-by-step/api-client";
import { describe, expect, it } from "vitest";

import { acceptRefusal, offerSentence } from "./messages";

const OFFER: OfferedMembership = {
  id: "3f0d7c1e-0000-4000-8000-000000000020",
  org_name: "Acme",
  role: "member",
};

describe("the pending-invitation banner", () => {
  it("names who wants this visitor, and as what", () => {
    expect(offerSentence(OFFER)).toBe("Acme invited you to join as a member.");
  });

  it("reads as English for the role that takes the other article", () => {
    expect(offerSentence({ ...OFFER, role: "admin" })).toBe(
      "Acme invited you to join as an admin.",
    );
  });
});

describe("a refusal on accepting", () => {
  it("is chosen by its code, never by its prose", () => {
    expect(acceptRefusal({ code: "invitation_not_found", message: "whatever the API said" })).toBe(
      "That Invitation is no longer standing. It was revoked, taken, or it expired.",
    );
  });

  it("falls back to something a person can act on when the code is not one it knows", () => {
    expect(acceptRefusal({ code: "meteorite" })).toBe(
      "Something went wrong. Try again in a moment.",
    );
    expect(acceptRefusal(undefined)).toBe("Something went wrong. Try again in a moment.");
  });
});
