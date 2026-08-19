/**
 * Everything the connect screen says, decided away from the DOM.
 *
 * The screen has three things to say and one of them is a refusal, so the
 * wording is worth reading back in a test rather than through a browser.
 */

/** Where the connect attempt has got to. */
export type ConnectState =
  | { kind: "waiting" }
  | { kind: "connected"; version: string }
  | { kind: "opened-by-hand" };

/** The one line at the top of the screen. */
export function connectHeadline(state: ConnectState): string {
  switch (state.kind) {
    case "waiting":
      return "Connecting your extension…";
    case "connected":
      return "Your extension is connected";
    case "opened-by-hand":
      return "Connect your extension";
  }
}

/** What to do about it, if anything. */
export function connectDetail(state: ConnectState): string {
  switch (state.kind) {
    case "waiting":
      return "Keep this tab open while the extension takes this instance's address.";
    case "connected":
      return "This browser can record Workflows on this instance now. You can close this tab.";
    case "opened-by-hand":
      return (
        "Open the extension from Chrome's toolbar, enter this instance's address, and choose " +
        "Connect. If you have done that and nothing happened, show a connect code below and " +
        "paste it into the extension."
      );
  }
}

const REFUSALS: Record<string, string> = {
  bad_code: "That code is no longer valid. Show a new one.",
};

const UNKNOWN_REFUSAL = "The code could not be shown. Try again in a moment.";

/** What the screen shows when asking for a code came back a refusal. */
export function codeRefusal(error: unknown): string {
  const code =
    typeof error === "object" && error !== null && "code" in error ? error.code : undefined;
  return (typeof code === "string" ? REFUSALS[code] : undefined) ?? UNKNOWN_REFUSAL;
}

/**
 * How long the code on the screen has left, in the words the screen uses.
 *
 * Minutes, because the code lives for ten of them and a second-by-second
 * countdown would be a clock nobody is watching.
 */
export function codeLifetime(expiresAt: string, now: Date): string {
  const left = Math.round((new Date(expiresAt).getTime() - now.getTime()) / 60_000);
  if (Number.isNaN(left) || left <= 0) {
    return "This code has expired. Show a new one.";
  }
  return left === 1
    ? "This code works once, and for one more minute."
    : `This code works once, and for the next ${left} minutes.`;
}
