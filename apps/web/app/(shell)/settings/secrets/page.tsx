"use client";

import {
  createSecret,
  deleteSecret,
  deleteSecretOverride,
  revealSecret,
  revealSecretOverride,
  setSecretOverride,
  updateSecret,
  type SecretSummary,
} from "@step-by-step/api-client";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useState } from "react";

import { loadSecrets, SECRETS_KEY } from "./queries";
import { REVEAL_DURATION_MS } from "./reveal";
import { deleteConsequence, usedBySummary } from "./usage";

import { Callout } from "@/components/primitives/callout";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { relativeTime } from "@/lib/relative-time";

export default function SecretsPage() {
  const secrets = useQuery({ queryKey: SECRETS_KEY, queryFn: loadSecrets });

  return (
    <div className="flex flex-col gap-4">
      <CreateSecret />
      {secrets.error ? <Callout tone="bad">The Secrets vault could not be loaded.</Callout> : null}
      {secrets.data?.length === 0 ? (
        <Card className="px-6 py-10 text-center">
          <p className="font-semibold">No Secrets yet</p>
          <p className="text-small text-mut">Create one above to keep a reusable value here.</p>
        </Card>
      ) : null}
      {secrets.data?.map((secret) => (
        <SecretRow key={secret.id} secret={secret} />
      ))}
    </div>
  );
}

function CreateSecret() {
  const cache = useQueryClient();
  const [name, setName] = useState("");
  const [value, setValue] = useState("");
  const create = useMutation({
    mutationFn: async () => {
      const answer = await createSecret({ body: { name, value } });
      if (answer.error) throw answer.error;
    },
    onSuccess: async () => {
      setName("");
      setValue("");
      await cache.invalidateQueries({ queryKey: SECRETS_KEY });
    },
  });

  return (
    <Card>
      <CardHeader>
        <CardTitle>Create a Secret</CardTitle>
      </CardHeader>
      <CardContent>
        <form
          className="grid gap-3 sm:grid-cols-[1fr_1fr_auto] sm:items-end"
          onSubmit={(event) => {
            event.preventDefault();
            create.mutate();
          }}
        >
          <Field id="new-secret-name" label="Name" value={name} onChange={setName} />
          <Field
            id="new-secret-value"
            label="Value"
            type="password"
            value={value}
            onChange={setValue}
          />
          <Button type="submit" disabled={create.isPending || !name.trim() || !value}>
            Create
          </Button>
        </form>
        {create.error ? <Callout tone="bad">That name is already in use.</Callout> : null}
      </CardContent>
    </Card>
  );
}

function Field({
  id,
  label,
  value,
  onChange,
  type = "text",
  required = true,
}: {
  id: string;
  label: string;
  value: string;
  onChange: (value: string) => void;
  type?: "text" | "password";
  required?: boolean;
}) {
  return (
    <div className="flex flex-col gap-2">
      <Label htmlFor={id}>{label}</Label>
      <Input
        id={id}
        type={type}
        value={value}
        required={required}
        autoComplete="off"
        onChange={(event) => {
          onChange(event.target.value);
        }}
      />
    </div>
  );
}

function SecretRow({ secret }: { secret: SecretSummary }) {
  const cache = useQueryClient();
  const [editing, setEditing] = useState(false);
  const [confirmingDelete, setConfirmingDelete] = useState(false);
  const [name, setName] = useState(secret.name);
  const [value, setValue] = useState("");
  const [ownValue, setOwnValue] = useState("");

  const change = useMutation({
    mutationFn: async () => {
      const body: { name?: string; value?: string } = {};
      if (name !== secret.name) body.name = name;
      if (value) body.value = value;
      const answer = await updateSecret({ path: { secret_id: secret.id }, body });
      if (answer.error) throw answer.error;
    },
    onSuccess: async () => {
      setEditing(false);
      setValue("");
      await cache.invalidateQueries({ queryKey: SECRETS_KEY });
    },
  });
  const remove = useMutation({
    mutationFn: async () => {
      const answer = await deleteSecret({ path: { secret_id: secret.id } });
      if (answer.error) throw answer.error;
    },
    onSuccess: async () => cache.invalidateQueries({ queryKey: SECRETS_KEY }),
  });
  const setOwn = useMutation({
    mutationFn: async () => {
      const answer = await setSecretOverride({
        path: { secret_id: secret.id },
        body: { value: ownValue },
      });
      if (answer.error) throw answer.error;
    },
    onSuccess: async () => {
      setOwnValue("");
      await cache.invalidateQueries({ queryKey: SECRETS_KEY });
    },
  });
  const clearOwn = useMutation({
    mutationFn: async () => {
      const answer = await deleteSecretOverride({ path: { secret_id: secret.id } });
      if (answer.error) throw answer.error;
    },
    onSuccess: async () => cache.invalidateQueries({ queryKey: SECRETS_KEY }),
  });

  return (
    <Card>
      <CardHeader>
        <CardTitle>{secret.name}</CardTitle>
        <p className="text-small text-mut">Updated {relativeTime(secret.updated_at)}</p>
        <p className="text-small text-mut">{usedBySummary(secret.used_by)}</p>
      </CardHeader>
      <CardContent className="flex flex-col gap-4">
        <RevealButton secretId={secret.id} own={false} />

        {editing ? (
          <form
            className="grid gap-3 sm:grid-cols-[1fr_1fr_auto] sm:items-end"
            onSubmit={(event) => {
              event.preventDefault();
              change.mutate();
            }}
          >
            <Field id={`name-${secret.id}`} label="Name" value={name} onChange={setName} />
            <Field
              id={`value-${secret.id}`}
              label="New value (leave blank to keep it)"
              type="password"
              value={value}
              onChange={setValue}
              required={false}
            />
            <Button type="submit" disabled={change.isPending || (!value && name === secret.name)}>
              Save
            </Button>
          </form>
        ) : (
          <Button variant="outline" className="self-start" onClick={() => setEditing(true)}>
            Edit
          </Button>
        )}

        <div className="flex flex-col gap-3 border-t border-line pt-4">
          <p className="font-medium">
            {secret.my_override
              ? `Using your own value · updated ${relativeTime(secret.my_override.updated_at)}`
              : "Use my own value"}
          </p>
          {secret.my_override ? <RevealButton secretId={secret.id} own /> : null}
          <form
            className="flex max-w-xl items-end gap-2"
            onSubmit={(event) => {
              event.preventDefault();
              setOwn.mutate();
            }}
          >
            <div className="grow">
              <Field
                id={`own-${secret.id}`}
                label={secret.my_override ? "Replace your value" : "Your value"}
                type="password"
                value={ownValue}
                onChange={setOwnValue}
              />
            </div>
            <Button type="submit" disabled={setOwn.isPending || !ownValue}>
              {secret.my_override ? "Update" : "Use my own value"}
            </Button>
            {secret.my_override ? (
              <Button
                type="button"
                variant="ghost"
                disabled={clearOwn.isPending}
                onClick={() => clearOwn.mutate()}
              >
                Clear
              </Button>
            ) : null}
          </form>
        </div>

        {confirmingDelete ? (
          <Callout
            tone="bad"
            title={`Delete ${secret.name}?`}
            actions={
              <div className="flex gap-2">
                <Button
                  size="sm"
                  variant="destructive"
                  disabled={remove.isPending}
                  onClick={() => remove.mutate()}
                >
                  Delete
                </Button>
                <Button size="sm" variant="ghost" onClick={() => setConfirmingDelete(false)}>
                  Cancel
                </Button>
              </div>
            }
          >
            {deleteConsequence(secret.name, secret.used_by)}
          </Callout>
        ) : (
          <Button
            variant="destructive"
            className="self-start"
            onClick={() => setConfirmingDelete(true)}
          >
            Delete
          </Button>
        )}
      </CardContent>
    </Card>
  );
}

function RevealButton({ secretId, own }: { secretId: string; own: boolean }) {
  const [value, setValue] = useState<string | null>(null);
  useEffect(() => {
    if (value === null) return;
    const timer = window.setTimeout(() => setValue(null), REVEAL_DURATION_MS);
    return () => window.clearTimeout(timer);
  }, [value]);

  const reveal = useMutation({
    mutationFn: async () => {
      const answer = own
        ? await revealSecretOverride({ path: { secret_id: secretId } })
        : await revealSecret({ path: { secret_id: secretId } });
      if (answer.error) throw answer.error;
      return answer.data.value;
    },
    onSuccess: setValue,
  });

  return (
    <div className="flex items-center gap-2">
      <span className="min-w-32 font-mono text-half">{value ?? "••••••••"}</span>
      <Button
        variant="outline"
        size="sm"
        disabled={reveal.isPending}
        onClick={() => reveal.mutate()}
      >
        {value === null ? "Reveal" : "Reveal again"}
      </Button>
    </div>
  );
}
