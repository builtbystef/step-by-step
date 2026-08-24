"use client";

import { getExtensionVersion, type ExtensionVersion } from "@step-by-step/api-client";
import { useQuery } from "@tanstack/react-query";
import { createContext, useContext, useEffect, useRef, useState, type ReactNode } from "react";

import { connectionState, probeExtension, watchWindowFocus } from "./extension-connection";
import type { ConnectionState } from "./labels";

export type ExtensionConnection = {
  state: ConnectionState | null;
  version: string | null;
  versions: ExtensionVersion | null;
  error: unknown;
};

const ExtensionConnectionContext = createContext<ExtensionConnection | null>(null);

/** One probe and one version request shared by every extension surface in the shell. */
export function ExtensionConnectionProvider({ children }: { children: ReactNode }) {
  const [version, setVersion] = useState<string | null | undefined>(undefined);
  const latestProbe = useRef(0);
  const versions = useQuery({
    queryKey: ["extension-version"],
    queryFn: async () => {
      const { data, error } = await getExtensionVersion();
      if (error) throw error;
      return data;
    },
  });

  useEffect(() => {
    const probe = () => {
      const sequence = latestProbe.current + 1;
      latestProbe.current = sequence;
      void probeExtension(window).then((answer) => {
        if (latestProbe.current === sequence) setVersion(answer);
      });
    };

    probe();
    return watchWindowFocus(window, probe);
  }, []);

  const instanceVersions = versions.data ?? null;
  const state =
    version === undefined || instanceVersions === null
      ? null
      : connectionState(version, instanceVersions.minimum_supported);

  return (
    <ExtensionConnectionContext.Provider
      value={{ state, version: version ?? null, versions: instanceVersions, error: versions.error }}
    >
      {children}
    </ExtensionConnectionContext.Provider>
  );
}

export function useExtensionConnection(): ExtensionConnection {
  const connection = useContext(ExtensionConnectionContext);
  if (connection === null) {
    throw new Error("useExtensionConnection must be used inside ExtensionConnectionProvider");
  }
  return connection;
}
