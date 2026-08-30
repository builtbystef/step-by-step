"use client";

import { Check, Download } from "lucide-react";
import { useEffect, useState } from "react";

import { ConnectionPill } from "@/components/primitives/connection-pill";
import { Callout } from "@/components/primitives/callout";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { useExtensionConnection } from "@/lib/extension-connection-context";

function useInstanceAddress(): string {
  const [address, setAddress] = useState("");
  useEffect(() => {
    setAddress(window.location.origin);
  }, []);
  return address;
}

export function InstallAndConnect({ compact = false }: { compact?: boolean }) {
  const connection = useExtensionConnection();
  const address = useInstanceAddress();

  return (
    <div className="flex flex-col gap-4">
      <div className="flex flex-wrap items-center gap-3">
        <Button render={<a href="/extension.zip" download />}>
          <Download className="size-4" />
          Download extension
        </Button>
        {connection.state === null ? (
          <span className="text-small text-mut">Checking this browser…</span>
        ) : (
          <ConnectionPill state={connection.state} version={connection.version ?? undefined} />
        )}
      </div>

      {compact ? null : (
        <Card className="gap-3 px-4">
          <h2 className="text-title font-semibold">Install the unpacked extension</h2>
          <ol className="grid gap-3 text-half text-ink sm:grid-cols-4">
            <li>
              <strong>1.</strong> Unzip the download.
            </li>
            <li>
              <strong>2.</strong> Open <code>chrome://extensions</code>.
            </li>
            <li>
              <strong>3.</strong> Turn on Developer mode.
            </li>
            <li>
              <strong>4.</strong> Choose Load unpacked and select the folder.
            </li>
          </ol>
        </Card>
      )}

      <div className="flex flex-col gap-1">
        <h2 className="text-title font-semibold">Connect this instance</h2>
        <p className="text-half text-mut">
          Open the extension popup and enter this instance&apos;s address
          {address ? (
            <>
              : <code className="text-ink">{address}</code>
            </>
          ) : (
            "."
          )}
        </p>
        <p className="text-small text-mut">
          The app cannot tell an extension that is not installed from one pointed at another
          instance. Both use these same install and connect steps.
        </p>
      </div>

      {connection.state === "out_of_date" ? (
        <Callout tone="warn">
          Update the extension before recording. This build is below the minimum supported version.
        </Callout>
      ) : connection.state === "connected" ? (
        <div className="flex items-center gap-2 text-half font-semibold text-ok">
          <Check className="size-4" /> This browser is ready to record.
        </div>
      ) : null}
    </div>
  );
}
