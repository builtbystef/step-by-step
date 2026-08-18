import { Suspense } from "react";

import { SignInScreen } from "./sign-in-screen";

/**
 * `/signin` — the one route outside the shell.
 *
 * The screen reads `next` from the query, which is a client-side fact; the
 * Suspense boundary is what lets the rest of the page be prerendered anyway.
 */
export default function SignInPage() {
  return (
    <Suspense>
      <SignInScreen />
    </Suspense>
  );
}
