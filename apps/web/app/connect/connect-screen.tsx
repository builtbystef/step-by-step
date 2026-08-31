"use client";

import { createExtensionConnectCode } from "@step-by-step/api-client";
import { useMutation } from "@tanstack/react-query";
import Image from "next/image";
import { useSearchParams } from "next/navigation";
import { useEffect, useState } from "react";

import {
  codeLifetime,
  codeRefusal,
  connectDetail,
  connectHeadline,
  type ConnectState,
} from "./messages";

import { Callout } from "@/components/primitives/callout";
import { ConnectionPill } from "@/components/primitives/connection-pill";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import {
  CONNECT_ACCEPTED,
  EXTENSION_READY,
  handshakeMessage,
  readExtensionMessage,
} from "@/lib/extension-protocol";

export function ConnectScreen() {
  const nonce = useSearchParams().get("nonce");
  const [state, setState] = useState<ConnectState>(
    nonce === null ? { kind: "opened-by-hand" } : { kind: "waiting" },
  );

  useEffect(() => {
    if (nonce === null) {
      return;
    }
    const origin = window.location.origin;
    const handOver = () => window.postMessage(handshakeMessage(nonce, origin), origin);

    const listen = (event: MessageEvent) => {
      if (event.source !== window || event.origin !== origin) {
        return;
      }
      const said = readExtensionMessage(event.data);
      if (said === null) {
        return;
      }
      if (said.type === EXTENSION_READY) {
        handOver();
      }
      if (said.type === CONNECT_ACCEPTED) {
        setState({ kind: "connected", version: said.version });
      }
    };

    window.addEventListener("message", listen);
    handOver();
    return () => window.removeEventListener("message", listen);
  }, [nonce]);

  const showCode = useMutation({
    mutationFn: async () => {
      const { data, error } = await createExtensionConnectCode();
      if (error) throw error;
      return data;
    },
  });

  return (
    <main className="mx-auto flex w-full max-w-[560px] flex-col gap-6 px-4 py-16">
      <div className="flex flex-col gap-2">
        <Image
          src="/brand/logo-icon.svg"
          alt="Step by Step"
          width={32}
          height={32}
          className="mb-2"
        />
        <h1 className="text-page">{connectHeadline(state)}</h1>
        <p className="text-small text-mut">{connectDetail(state)}</p>
        {state.kind === "connected" ? (
          <ConnectionPill state="connected" version={state.version} className="self-start" />
        ) : null}
      </div>

      {state.kind === "connected" ? null : (
        <Card>
          <CardContent className="flex flex-col gap-3">
            <h2 className="text-body font-semibold">Connect with a code instead</h2>
            <p className="text-small text-mut">
              If Chrome did not let the extension onto this page, show a code here and paste it into
              the extension&rsquo;s popup.
            </p>
            {showCode.data ? (
              <div className="flex flex-col gap-1">
                <p className="font-mono text-page tracking-widest">{showCode.data.code}</p>
                <p className="text-small text-mut">
                  {codeLifetime(showCode.data.expires_at, new Date())}
                </p>
              </div>
            ) : null}
            {showCode.error ? <Callout tone="bad">{codeRefusal(showCode.error)}</Callout> : null}
            <Button
              type="button"
              variant={showCode.data ? "outline" : "default"}
              className="self-start"
              disabled={showCode.isPending}
              onClick={() => {
                showCode.mutate();
              }}
            >
              {showCode.data ? "Show another code" : "Show a connect code"}
            </Button>
          </CardContent>
        </Card>
      )}
    </main>
  );
}
