import type { Metadata } from "next";
import type { ReactNode } from "react";

import { Providers } from "./providers";

import { THEME_BOOT_SCRIPT } from "@/lib/theme";

import "./globals.css";

export const metadata: Metadata = {
  title: "Step by Step",
  description: "Browser workflows that run themselves, and ask when they need you.",
};

export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    // The boot script may add `dark` before React sees the tree; that is expected.
    <html lang="en" suppressHydrationWarning>
      <head>
        <script dangerouslySetInnerHTML={{ __html: THEME_BOOT_SCRIPT }} />
      </head>
      <body>
        <Providers>{children}</Providers>
      </body>
    </html>
  );
}
