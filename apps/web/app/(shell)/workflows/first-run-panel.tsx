"use client";

import { Check } from "lucide-react";

import { InstallAndConnect } from "@/components/extension/install-and-connect";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { useExtensionConnection } from "@/lib/extension-connection-context";

/** The two independent first steps: connection helps recording, but never gates naming. */
export function FirstRunPanel({ onCreate }: { onCreate: () => void }) {
  const connection = useExtensionConnection();
  const connected = connection.state === "connected";

  return (
    <div className="grid gap-4">
      <Card className="px-4">
        <div className="flex items-start gap-3">
          <span className="flex size-6 shrink-0 items-center justify-center rounded-full bg-accent-bg text-small font-semibold text-accent">
            {connected ? <Check className="size-4 text-ok" /> : "1"}
          </span>
          <div className="flex min-w-0 flex-1 flex-col gap-3">
            <h2 className="text-title font-semibold">
              {connected ? "Browser extension connected" : "Install the browser extension"}
            </h2>
            {connected ? null : <InstallAndConnect />}
          </div>
        </div>
      </Card>

      <Card className="px-4">
        <div className="flex items-start gap-3">
          <span className="flex size-6 shrink-0 items-center justify-center rounded-full bg-accent-bg text-small font-semibold text-accent">
            2
          </span>
          <div className="flex flex-1 flex-col items-start gap-2">
            <h2 className="text-title font-semibold">Create your first workflow</h2>
            <p className="text-half text-mut">
              Name the Workflow now. You can install or connect the extension before recording.
            </p>
            <Button onClick={onCreate}>New workflow</Button>
          </div>
        </div>
      </Card>
    </div>
  );
}
