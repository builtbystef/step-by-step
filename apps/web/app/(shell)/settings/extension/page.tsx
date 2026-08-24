"use client";

import { InstallAndConnect } from "@/components/extension/install-and-connect";
import { Callout } from "@/components/primitives/callout";
import { Card } from "@/components/ui/card";
import { useExtensionConnection } from "@/lib/extension-connection-context";

/** `/settings/extension` — installation, connection, and compatibility in one place. */
export default function BrowserExtensionPage() {
  const connection = useExtensionConnection();

  return (
    <>
      <div>
        <h2 className="text-title font-semibold">Browser extension</h2>
        <p className="text-half text-mut">
          Install the paired build and point it at this instance.
        </p>
      </div>

      {connection.error ? (
        <Callout tone="bad">The instance&apos;s extension versions could not be loaded.</Callout>
      ) : null}

      <InstallAndConnect />

      <Card className="gap-2 px-4">
        <h2 className="text-title font-semibold">Versions</h2>
        <dl className="grid grid-cols-[auto_1fr] gap-x-6 gap-y-1 text-half">
          <dt className="text-mut">This instance</dt>
          <dd className="font-mono">{connection.versions?.current ?? "Checking…"}</dd>
          <dt className="text-mut">Minimum supported</dt>
          <dd className="font-mono">{connection.versions?.minimum_supported ?? "Checking…"}</dd>
          <dt className="text-mut">This browser</dt>
          <dd className="font-mono">{connection.version ?? "Not connected"}</dd>
        </dl>
      </Card>
    </>
  );
}
