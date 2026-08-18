import type { SignupMode } from "@step-by-step/api-client";

/**
 * Everything the sign-in screen says that depends on an answer: what this
 * instance does with a new address, and what each refusal means.
 *
 * A refusal is chosen by its `code` and never by its prose — the backend's
 * message is a machine-readable fact's label, not a sentence written for
 * whoever is standing at the screen.
 */

const REFUSALS: Record<string, string> = {
  bad_code:
    "That code is wrong or has expired. Check the code in the email, or send yourself a new one.",
  code_exhausted:
    "That code has had too many wrong tries and no longer works. Send yourself a new Sign-in Code.",
  rate_limited: "Too many codes have been asked for. Wait a few minutes, then try again.",
  signup_closed:
    "This instance does not create accounts on its own — new accounts join by Invitation. " +
    "Ask an owner or admin of an Organization to invite this address.",
};

const UNKNOWN_REFUSAL = "Something went wrong. Try again in a moment.";

/** What the screen shows for a refusal, or for anything else that came back. */
export function refusalMessage(error: unknown): string {
  const code =
    typeof error === "object" && error !== null && "code" in error ? error.code : undefined;
  return (typeof code === "string" ? REFUSALS[code] : undefined) ?? UNKNOWN_REFUSAL;
}

const SIGNUP_NOTES: Record<SignupMode, string> = {
  open: "No account yet? Entering the code creates one.",
  invite_only: "Sign-in only — new accounts join this instance by Invitation.",
};

/**
 * The grey line under the address field, which the instance decides.
 *
 * Empty until `GET /api/instance` has answered: a promise of an account on an
 * invite-only instance, corrected a moment later, is worse than a beat of
 * silence.
 */
export function emailStepNote(mode: SignupMode | undefined): string {
  return mode === undefined ? "" : SIGNUP_NOTES[mode];
}
