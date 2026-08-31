"use client";

import { getInstance, requestSigninCode, verifySigninCode } from "@step-by-step/api-client";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import Image from "next/image";
import { useRouter, useSearchParams } from "next/navigation";
import { useEffect, useState, type ReactNode } from "react";

import { emailStepNote, refusalMessage } from "./messages";

import { Callout } from "@/components/primitives/callout";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { landingAfterSignIn, resolveGate, SIGN_IN_PATH } from "@/lib/gate";
import { IDENTITY_KEY, identityQuery } from "@/lib/identity";

const INSTANCE_QUERY = {
  queryKey: ["instance"] as const,
  staleTime: Number.POSITIVE_INFINITY,
  queryFn: async () => (await getInstance()).data ?? null,
};

export function SignInScreen() {
  const router = useRouter();
  const cache = useQueryClient();
  const next = useSearchParams().get("next");

  const [email, setEmail] = useState("");
  const [code, setCode] = useState("");
  const [sent, setSent] = useState(false);

  const identity = useQuery(identityQuery());
  const instance = useQuery(INSTANCE_QUERY);

  const arrived = resolveGate(identity.data ?? null, null, SIGN_IN_PATH).kind === "redirect";
  useEffect(() => {
    if (arrived) {
      router.replace(landingAfterSignIn(next));
    }
  }, [arrived, next, router]);

  const askForCode = useMutation({
    mutationFn: async () => {
      const { error } = await requestSigninCode({ body: { email } });
      if (error) throw error;
    },
    onSuccess: () => {
      setCode("");
      setSent(true);
    },
  });

  const signIn = useMutation({
    mutationFn: async () => {
      const { data, error } = await verifySigninCode({ body: { email, code } });
      if (error) throw error;
      return data;
    },
    onSuccess: async () => {
      await cache.invalidateQueries({ queryKey: IDENTITY_KEY });
    },
  });

  if (identity.isPending || arrived) {
    return <Screen />;
  }

  const note = emailStepNote(instance.data?.signup_mode);

  const refused = signIn.error ?? askForCode.error;

  return (
    <Screen>
      {sent ? (
        <form
          className="flex flex-col gap-3"
          onSubmit={(submitted) => {
            submitted.preventDefault();
            signIn.mutate();
          }}
        >
          <Label htmlFor="code">Sign-in Code</Label>
          <p className="text-small text-mut">
            We sent a 6-digit code to <span className="text-ink">{email}</span>. It works once, and
            it expires in 10 minutes.
          </p>
          <Input
            id="code"
            value={code}
            autoFocus
            inputMode="numeric"
            autoComplete="one-time-code"
            maxLength={6}
            onChange={(typed) => setCode(typed.target.value.trim())}
          />
          {refused ? <Callout tone="bad">{refusalMessage(refused)}</Callout> : null}
          <Button type="submit" disabled={signIn.isPending || code.length === 0}>
            Sign in
          </Button>
          <div className="flex items-center justify-between">
            <Button
              type="button"
              variant="link"
              size="sm"
              className="px-0 text-small"
              disabled={askForCode.isPending}
              onClick={() => {
                signIn.reset();
                askForCode.mutate();
              }}
            >
              Send a new code
            </Button>
            <Button
              type="button"
              variant="link"
              size="sm"
              className="px-0 text-small"
              onClick={() => {
                signIn.reset();
                askForCode.reset();
                setCode("");
                setSent(false);
              }}
            >
              Use a different email
            </Button>
          </div>
        </form>
      ) : (
        <form
          className="flex flex-col gap-3"
          onSubmit={(submitted) => {
            submitted.preventDefault();
            askForCode.mutate();
          }}
        >
          <Label htmlFor="email">Email</Label>
          <Input
            id="email"
            type="email"
            value={email}
            autoFocus
            autoComplete="email"
            onChange={(typed) => setEmail(typed.target.value.trim())}
          />
          {note ? <p className="text-body text-mut">{note}</p> : null}
          {askForCode.error ? (
            <Callout tone="bad">{refusalMessage(askForCode.error)}</Callout>
          ) : null}
          <Button type="submit" disabled={askForCode.isPending || email.length === 0}>
            Continue
          </Button>
        </form>
      )}
    </Screen>
  );
}

function Screen({ children }: { children?: ReactNode }) {
  return (
    <main className="flex min-h-screen items-center justify-center px-4 py-12">
      <Card className="w-full max-w-[400px] [--card-spacing:--spacing(6)]">
        <CardContent className="flex flex-col gap-6">
          <h1 className="flex justify-center">
            <Image
              src="/brand/logo-vertical.svg"
              alt="Step by Step"
              width={196}
              height={108}
              priority
            />
          </h1>
          {children}
        </CardContent>
      </Card>
    </main>
  );
}
