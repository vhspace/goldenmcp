/** Web app environment — local dev, Vercel production (GH #106). */

export function firstEnv(...keys: string[]): string | undefined {
  for (const key of keys) {
    const value = process.env[key]?.trim();
    if (value) return value;
  }
  return undefined;
}

export function arcRpcUrl(): string {
  return (
    firstEnv("NEXT_PUBLIC_ARC_RPC_URL", "ARC_RPC_URL", "ARC_TESTNET_RPC_URL") ??
    "https://rpc.testnet.arc.network"
  );
}

export function registryAddress(): string {
  return firstEnv("NEXT_PUBLIC_REGISTRY_ADDRESS", "ARC_REGISTRY_ADDRESS") ?? "";
}

export function ensRpcUrl(): string {
  return (
    firstEnv("NEXT_PUBLIC_ENS_RPC_URL", "ENS_RPC_URL") ??
    "https://ethereum-sepolia-rpc.publicnode.com"
  );
}

export function walrusAggregatorUrl(): string {
  return (
    firstEnv("NEXT_PUBLIC_WALRUS_AGGREGATOR_URL", "WALRUS_AGGREGATOR_URL") ??
    "https://aggregator.walrus-testnet.walrus.space"
  );
}

export function evalRunnerUrl(): string {
  const explicit = firstEnv("EVAL_RUNNER_URL", "EVAL_RUNNER_PUBLIC_URL");
  if (explicit) return explicit.replace(/\/$/, "");
  const host = firstEnv("EVAL_RUNNER_HOST") ?? "127.0.0.1";
  const port = firstEnv("EVAL_RUNNER_PORT") ?? "8090";
  return `http://${host}:${port}`;
}

export function marketplaceUrl(): string {
  const url =
    firstEnv("MARKETPLACE_URL", "NEXT_PUBLIC_MARKETPLACE_URL") ?? "http://localhost:8091";
  if (process.env.VERCEL && /localhost|127\.0\.0\.1/.test(url)) {
    throw new Error(
      "MARKETPLACE_URL must be a public HTTPS URL on Vercel — configure it in Project → Environment Variables",
    );
  }
  return url.replace(/\/$/, "");
}

export function webAgentUrl(): string {
  const explicit = firstEnv("WEB_AGENT_URL", "WEB_AGENT_PUBLIC_URL");
  if (explicit) return explicit.replace(/\/$/, "");
  const host = firstEnv("WEB_AGENT_HOST") ?? "127.0.0.1";
  const port = firstEnv("WEB_AGENT_PORT") ?? "8092";
  return `http://${host}:${port}`;
}

export function webAgentApiKey(): string | undefined {
  return firstEnv("WEB_AGENT_API_KEY");
}

/** Keys injected via next.config `env` for client + server bundles. */
export function webEnvConfig(): Record<string, string> {
  const arc = arcRpcUrl();
  return {
    NEXT_PUBLIC_ARC_RPC_URL: arc,
    NEXT_PUBLIC_REGISTRY_ADDRESS: registryAddress(),
    NEXT_PUBLIC_ENS_RPC_URL: ensRpcUrl(),
    NEXT_PUBLIC_WALRUS_AGGREGATOR_URL: walrusAggregatorUrl(),
    ARC_RPC_URL: arc,
    ARC_REGISTRY_ADDRESS: registryAddress(),
    ARC_TESTNET_RPC_URL: firstEnv("ARC_TESTNET_RPC_URL") ?? arc,
    ENS_RPC_URL: ensRpcUrl(),
    WALRUS_AGGREGATOR_URL: walrusAggregatorUrl(),
    MARKETPLACE_URL: marketplaceUrl(),
    EVAL_RUNNER_URL: evalRunnerUrl(),
    EVAL_RUNNER_HOST: firstEnv("EVAL_RUNNER_HOST") ?? "127.0.0.1",
    EVAL_RUNNER_PORT: firstEnv("EVAL_RUNNER_PORT") ?? "8090",
    WEB_AGENT_URL: webAgentUrl(),
    WEB_AGENT_HOST: firstEnv("WEB_AGENT_HOST") ?? "127.0.0.1",
    WEB_AGENT_PORT: firstEnv("WEB_AGENT_PORT") ?? "8092",
  };
}
