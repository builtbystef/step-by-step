"use client";

import { useSyncExternalStore } from "react";

import { rememberedTheme, watchTheme, type ThemeChoice } from "./theme";

function serverChoice(): ThemeChoice {
  return "system";
}

export function useThemeChoice(): ThemeChoice {
  return useSyncExternalStore(watchTheme, rememberedTheme, serverChoice);
}
