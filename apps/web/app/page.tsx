"use client";

import { getGreeting, getHealth } from "@step-by-step/api-client";
import { useEffect, useState } from "react";

export default function Home() {
  const [status, setStatus] = useState("checking…");
  const [greeting, setGreeting] = useState("");

  useEffect(() => {
    getHealth()
      .then(({ data }) => setStatus(data?.status ?? "no data"))
      .catch(() => setStatus("api unreachable"));
    getGreeting({ path: { name: "Step by Step" } })
      .then(({ data }) => setGreeting(data?.message ?? ""))
      .catch(() => setGreeting(""));
  }, []);

  return (
    <main>
      <h1>Step by Step</h1>
      <p>
        API health: <strong>{status}</strong>
      </p>
      {greeting && <p>{greeting}</p>}
    </main>
  );
}
