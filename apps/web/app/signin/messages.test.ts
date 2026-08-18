import { describe, expect, it } from "vitest";

import { emailStepNote, refusalMessage } from "./messages";

/**
 * What the sign-in screen says, tested where it is decided rather than where
 * it is drawn. Each refusal the contract can answer with has to read as its
 * own thing: a visitor who cannot tell a wrong code from an exhausted one
 * cannot tell which of them to do something about.
 */

const REFUSALS = ["bad_code", "code_exhausted", "rate_limited", "signup_closed"];

describe("what a refusal says", () => {
  it("says something different for every refusal", () => {
    const said = REFUSALS.map((code) => refusalMessage({ code, message: "" }));

    expect(new Set(said).size).toBe(REFUSALS.length);
  });

  it("tells an exhausted code from a wrong one by offering a new one", () => {
    expect(refusalMessage({ code: "bad_code", message: "" })).toMatch(/wrong|expired/i);
    expect(refusalMessage({ code: "code_exhausted", message: "" })).toMatch(/new Sign-in Code/);
  });

  it("says plainly that new accounts join by Invitation", () => {
    expect(refusalMessage({ code: "signup_closed", message: "" })).toMatch(/by Invitation/);
  });

  it("asks for patience when the instance is rate limiting", () => {
    expect(refusalMessage({ code: "rate_limited", message: "" })).toMatch(/wait/i);
  });

  it("never repeats the backend's own prose, which is not written for anyone", () => {
    expect(refusalMessage({ code: "bad_code", message: "that code is not usable" })).not.toMatch(
      /that code is not usable/,
    );
  });

  it("has something to say about an answer it does not know", () => {
    expect(refusalMessage(new TypeError("offline"))).not.toBe("");
    expect(refusalMessage({ detail: [] })).not.toBe("");
  });
});

describe("what the email step says about this instance", () => {
  it("promises an account when the instance is open", () => {
    expect(emailStepNote("open")).toMatch(/account/i);
    expect(emailStepNote("open")).not.toMatch(/Invitation/);
  });

  it("says new accounts join by Invitation when the instance is invite-only", () => {
    expect(emailStepNote("invite_only")).toMatch(/by Invitation/);
  });

  it("says nothing at all until the instance has answered", () => {
    expect(emailStepNote(undefined)).toBe("");
  });
});
