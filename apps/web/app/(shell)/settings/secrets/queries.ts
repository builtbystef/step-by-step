import { listSecrets, type SecretSummary } from "@step-by-step/api-client";

export const SECRETS_KEY = ["secrets"] as const;

export async function loadSecrets(): Promise<SecretSummary[]> {
  const { data, error } = await listSecrets();
  if (error) throw error;
  return data;
}
