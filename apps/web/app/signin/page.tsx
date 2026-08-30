import { Suspense } from "react";

import { SignInScreen } from "./sign-in-screen";

export default function SignInPage() {
  return (
    <Suspense>
      <SignInScreen />
    </Suspense>
  );
}
