"use client";

import { useState } from "react";

export default function ENSResolverPage() {
  const [name, setName] = useState("");
  const [result, setResult] = useState<Record<string, string> | null>(null);
  const [error, setError] = useState("");

  async function resolve() {
    setError("");
    setResult(null);
    try {
      const res = await fetch(`/api/ens?name=${encodeURIComponent(name)}`);
      if (!res.ok) {
        const body = await res.json();
        throw new Error(body.error || res.statusText);
      }
      setResult(await res.json());
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    }
  }

  return (
    <div>
      <h1>ENS Resolver</h1>
      <p>Live ENS text record resolution — no hard-coded names.</p>
      <div style={{ display: "flex", gap: "0.5rem", marginTop: "1rem" }}>
        <input
          value={name}
          onChange={(e) => setName(e.target.value)}
          placeholder="lifi-quote.goldenmcp.eth"
          style={{ flex: 1, padding: "0.5rem", background: "#111", border: "1px solid #333", color: "#fff" }}
        />
        <button onClick={resolve} style={{ padding: "0.5rem 1rem" }}>
          Resolve
        </button>
      </div>
      {error && <p style={{ color: "#f66", marginTop: "1rem" }}>{error}</p>}
      {result && (
        <dl style={{ marginTop: "1rem" }}>
          {Object.entries(result).map(([k, v]) => (
            <div key={k}>
              <dt style={{ color: "#888" }}>{k}</dt>
              <dd style={{ marginBottom: "0.5rem" }}>
                <code>{v}</code>
              </dd>
            </div>
          ))}
        </dl>
      )}
    </div>
  );
}
