"use client";

import { getAttention, type Attention } from "@step-by-step/api-client";
import { useQuery } from "@tanstack/react-query";
import { createContext, useContext, type ReactNode } from "react";

import { ATTENTION_KEY, attentionRefetchInterval } from "./attention";

const AttentionContext = createContext<Attention | null>(null);

export function AttentionProvider({ children }: { children: ReactNode }) {
  const attention = useQuery({
    queryKey: ATTENTION_KEY,
    queryFn: async () => {
      const { data, error } = await getAttention();
      if (error) throw error;
      return data;
    },
    refetchInterval: () => attentionRefetchInterval(document.visibilityState),
    refetchOnWindowFocus: true,
    retry: 1,
    staleTime: 0,
  });

  return (
    <AttentionContext.Provider value={attention.data ?? null}>{children}</AttentionContext.Provider>
  );
}

export function useAttention(): Attention | null {
  return useContext(AttentionContext);
}
