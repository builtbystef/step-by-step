import type { AuthStateScope } from "@step-by-step/api-client";

export function savedLoginScope(scope: AuthStateScope): string {
  return scope === "organization" ? "Organization login" : "Your login";
}
