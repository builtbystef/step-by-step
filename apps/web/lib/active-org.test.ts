import type { Account, OrganizationMembership } from "@step-by-step/api-client";
import { describe, expect, it } from "vitest";

import {
  activeOrganization,
  offersASwitcher,
  rememberOrganization,
  chooseOrganization,
  organizationChoice,
  rememberedOrganization,
  watchOrganizationChoice,
} from "./active-org";

const ACME: OrganizationMembership = {
  id: "3f0d7c1e-0000-4000-8000-000000000010",
  name: "Acme",
  role: "owner",
};
const BOLT: OrganizationMembership = {
  id: "3f0d7c1e-0000-4000-8000-000000000011",
  name: "Bolt",
  role: "member",
};

function accountIn(...orgs: OrganizationMembership[]): Account {
  return {
    id: "3f0d7c1e-0000-4000-8000-000000000001",
    email: "ada@example.com",
    display_name: "Ada",
    orgs,
    invitations: [],
  };
}

function memory(entries: Record<string, string> = {}): Storage {
  const held = new Map(Object.entries(entries));
  return {
    get length() {
      return held.size;
    },
    clear: () => held.clear(),
    getItem: (key) => held.get(key) ?? null,
    key: (index) => [...held.keys()][index] ?? null,
    removeItem: (key) => void held.delete(key),
    setItem: (key, value) => void held.set(key, value),
  };
}

describe("the active Organization", () => {
  it("is what this browser remembered", () => {
    expect(activeOrganization(accountIn(ACME, BOLT), BOLT.id)).toEqual(BOLT);
  });

  it("is the first one when nothing was remembered", () => {
    expect(activeOrganization(accountIn(ACME, BOLT), null)).toEqual(ACME);
  });

  it("falls back when the remembered Organization is no longer one of theirs", () => {
    expect(activeOrganization(accountIn(ACME), BOLT.id)).toEqual(ACME);
  });

  it("is nobody's when there is no session", () => {
    expect(activeOrganization(null, ACME.id)).toBeNull();
  });

  it("is nobody's when the account is in no Organization at all", () => {
    expect(activeOrganization(accountIn(), null)).toBeNull();
  });
});

describe("the switcher", () => {
  it("is offered to somebody who is in more than one Organization", () => {
    expect(offersASwitcher(accountIn(ACME, BOLT))).toBe(true);
  });

  it("is not offered when there is only one to be in — the name is the whole fact", () => {
    expect(offersASwitcher(accountIn(ACME))).toBe(false);
  });
});

describe("remembering the choice", () => {
  it("survives a reload, which is what a browser's own memory is for", () => {
    const browser = memory();

    rememberOrganization(BOLT.id, browser);

    expect(rememberedOrganization(browser)).toBe(BOLT.id);
  });

  it("remembers nothing before a choice is made", () => {
    expect(rememberedOrganization(memory())).toBeNull();
  });

  it("is given up when the Organization is, so the next answer is a fresh one", () => {
    const browser = memory({ [""]: "" });
    rememberOrganization(BOLT.id, browser);

    rememberOrganization(null, browser);

    expect(rememberedOrganization(browser)).toBeNull();
  });

  it("says nothing when this browser has no memory to speak of", () => {
    expect(rememberedOrganization(undefined)).toBeNull();
    expect(() => {
      rememberOrganization(BOLT.id, undefined);
    }).not.toThrow();
  });
});

describe("the choice, as the app holds it", () => {
  it("is what was last chosen, and what a reload would find", () => {
    const browser = memory();

    chooseOrganization(BOLT.id, browser);

    expect(organizationChoice(browser)).toBe(BOLT.id);
    expect(rememberedOrganization(browser)).toBe(BOLT.id);
  });

  it("tells whoever is watching, because switching re-scopes every screen at once", () => {
    const browser = memory();
    const heard: string[] = [];
    const stop = watchOrganizationChoice(() => heard.push(organizationChoice(browser) ?? "none"));

    chooseOrganization(BOLT.id, browser);
    chooseOrganization(null, browser);

    stop();
    expect(heard).toEqual([BOLT.id, "none"]);
  });

  it("stops telling a watcher that has gone", () => {
    const browser = memory();
    const heard: string[] = [];
    watchOrganizationChoice(() => heard.push("heard"))();

    chooseOrganization(ACME.id, browser);

    expect(heard).toEqual([]);
  });
});
