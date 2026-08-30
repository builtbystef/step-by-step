import { client } from "@step-by-step/api-client";

import { resolveGate } from "./gate";

const ORGANIZATION_HEADER = "X-Organization";

export function installUnauthorizedRedirect(
  navigate: (to: string) => void,
  here: () => string = currentPath,
): () => void {
  const installed = client.interceptors.response.use((response: Response) => {
    if (response.status === 401) {
      const gate = resolveGate(null, null, here());
      if (gate.kind === "redirect") {
        navigate(gate.to);
      }
    }
    return response;
  });

  return () => client.interceptors.response.eject(installed);
}

function currentPath(): string {
  return `${window.location.pathname}${window.location.search}`;
}

export function installOrganizationHeader(activeOrganization: () => string | null): () => void {
  const installed = client.interceptors.request.use((request: Request) => {
    const active = activeOrganization();
    if (active !== null) {
      request.headers.set(ORGANIZATION_HEADER, active);
    }
    return request;
  });

  return () => client.interceptors.request.eject(installed);
}

export function installMembershipLapsed(onLapsed: () => void): () => void {
  const installed = client.interceptors.response.use(async (response: Response) => {
    if (response.status === 403 && (await refusalCode(response)) === "not_a_member") {
      onLapsed();
    }
    return response;
  });

  return () => client.interceptors.response.eject(installed);
}

async function refusalCode(response: Response): Promise<string | undefined> {
  try {
    // Preserve the original body for the caller.
    const body: unknown = await response.clone().json();
    return typeof body === "object" && body !== null && "code" in body
      ? String(body.code)
      : undefined;
  } catch {
    return undefined;
  }
}
