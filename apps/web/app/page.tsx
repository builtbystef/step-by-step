"use client";

import {
  getCurrentAccount,
  requestSigninCode,
  signOut,
  verifySigninCode,
} from "@step-by-step/api-client";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";

import { Button } from "@/components/ui/button";
import { Callout } from "@/components/primitives/callout";

/**
 * Signing in, and seeing who you are once you have.
 *
 * The minimal screen the accounts tracer needs: one two-step form — the
 * address, then the code that address received — for a first visit and a
 * returning one alike, because they are the same flow. The sign-in screen
 * proper, with the route gate and the fetch wrapper, replaces this page.
 *
 * Every call goes through the generated client, which reaches the backend
 * through the one-origin proxy; nothing here knows an API host.
 */

const ACCOUNT = ["account"] as const;

/** What the screen says about each refusal the contract can answer with. */
const REFUSALS: Record<string, string> = {
  bad_code: "That code is wrong, already used, or expired. Ask for a new one.",
  signup_closed: "This instance does not accept new accounts.",
};

function refusalOf(error: unknown): string {
  const code =
    typeof error === "object" && error !== null && "code" in error ? error.code : undefined;
  return (typeof code === "string" ? REFUSALS[code] : undefined) ?? "Something went wrong.";
}

const FIELD =
  "w-full rounded-lg border border-line bg-panel px-3 py-2 text-body text-ink outline-none focus:border-accent";

export default function Home() {
  const queryClient = useQueryClient();
  const [email, setEmail] = useState("");
  const [code, setCode] = useState("");
  const [codeSent, setCodeSent] = useState(false);

  const account = useQuery({
    queryKey: ACCOUNT,
    retry: false,
    queryFn: async () => (await getCurrentAccount()).data ?? null,
  });

  const askForCode = useMutation({
    mutationFn: async () => {
      const { error } = await requestSigninCode({ body: { email } });
      if (error) throw error;
    },
    onSuccess: () => setCodeSent(true),
  });

  const signIn = useMutation({
    mutationFn: async () => {
      const { data, error } = await verifySigninCode({ body: { email, code } });
      if (error) throw error;
      return data;
    },
    onSuccess: async () => {
      setCode("");
      setCodeSent(false);
      await queryClient.invalidateQueries({ queryKey: ACCOUNT });
    },
  });

  const leave = useMutation({
    mutationFn: async () => {
      await signOut();
    },
    onSuccess: async () => {
      setEmail("");
      await queryClient.invalidateQueries({ queryKey: ACCOUNT });
    },
  });

  if (account.isPending) {
    return <main className="p-6 text-mut">Loading…</main>;
  }

  if (account.data) {
    return (
      <main className="mx-auto flex max-w-[400px] flex-col gap-4 p-6">
        <h1 className="text-page">Step by Step</h1>
        <p className="text-body text-ink">
          Signed in as <strong>{account.data.email}</strong>
        </p>
        <ul className="flex flex-col gap-1 text-small text-mut">
          {account.data.orgs.map((org) => (
            <li key={org.id}>
              {org.name} — {org.role}
            </li>
          ))}
        </ul>
        <Button variant="outline" onClick={() => leave.mutate()} disabled={leave.isPending}>
          Sign out
        </Button>
      </main>
    );
  }

  return (
    <main className="mx-auto flex max-w-[400px] flex-col gap-4 p-6">
      <h1 className="text-page">Step by Step</h1>

      {codeSent ? (
        <form
          className="flex flex-col gap-3"
          onSubmit={(submitted) => {
            submitted.preventDefault();
            signIn.mutate();
          }}
        >
          <label className="text-small text-mut" htmlFor="code">
            We sent a 6-digit code to {email}.
          </label>
          <input
            id="code"
            className={FIELD}
            value={code}
            inputMode="numeric"
            autoComplete="one-time-code"
            onChange={(typed) => setCode(typed.target.value)}
          />
          {signIn.error ? <Callout tone="bad">{refusalOf(signIn.error)}</Callout> : null}
          <Button type="submit" disabled={signIn.isPending || code.length === 0}>
            Sign in
          </Button>
          <Button
            type="button"
            variant="ghost"
            onClick={() => {
              setCode("");
              setCodeSent(false);
            }}
          >
            Use another address
          </Button>
        </form>
      ) : (
        <form
          className="flex flex-col gap-3"
          onSubmit={(submitted) => {
            submitted.preventDefault();
            askForCode.mutate();
          }}
        >
          <label className="text-small text-mut" htmlFor="email">
            Enter your email and we will send you a sign-in code.
          </label>
          <input
            id="email"
            className={FIELD}
            type="email"
            value={email}
            autoComplete="email"
            onChange={(typed) => setEmail(typed.target.value)}
          />
          {askForCode.error ? <Callout tone="bad">{refusalOf(askForCode.error)}</Callout> : null}
          <Button type="submit" disabled={askForCode.isPending || email.length === 0}>
            Continue
          </Button>
        </form>
      )}
    </main>
  );
}
