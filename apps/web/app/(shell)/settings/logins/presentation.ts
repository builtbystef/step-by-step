import type { AuthStateScope } from "@step-by-step/api-client";

/** User-facing names for the two Auth State destinations. */
export function savedLoginScope(scope: AuthStateScope): string {
  return scope === "organization" ? "Organization login" : "Your login";
}
