/** Build-time env for next.config — process.env (Vercel) wins over repo-root .env. */
const fs = require("fs");
const path = require("path");

function loadRootEnvFile() {
  const envPath = path.resolve(__dirname, "../..", ".env");
  if (!fs.existsSync(envPath)) return {};

  const vars = {};
  for (const line of fs.readFileSync(envPath, "utf8").split("\n")) {
    const trimmed = line.trim();
    if (!trimmed || trimmed.startsWith("#")) continue;
    const eq = trimmed.indexOf("=");
    if (eq <= 0) continue;
    const key = trimmed.slice(0, eq).trim();
    let value = trimmed.slice(eq + 1).trim();
    if (
      (value.startsWith('"') && value.endsWith('"')) ||
      (value.startsWith("'") && value.endsWith("'"))
    ) {
      value = value.slice(1, -1);
    }
    if (value) vars[key] = value;
  }
  return vars;
}

function pick(rootEnv, ...keys) {
  for (const key of keys) {
    const value = process.env[key]?.trim();
    if (value) return value;
  }
  for (const key of keys) {
    const value = rootEnv[key];
    if (value) return value;
  }
  return undefined;
}

function evalRunnerUrl(rootEnv) {
  const explicit = pick(rootEnv, "EVAL_RUNNER_URL", "EVAL_RUNNER_PUBLIC_URL");
  if (explicit) return explicit.replace(/\/$/, "");
  const host = pick(rootEnv, "EVAL_RUNNER_HOST") ?? "127.0.0.1";
  const port = pick(rootEnv, "EVAL_RUNNER_PORT") ?? "8090";
  return `http://${host}:${port}`;
}

function marketplaceUrl(rootEnv) {
  return (
    pick(rootEnv, "MARKETPLACE_URL", "NEXT_PUBLIC_MARKETPLACE_URL") ??
    "http://localhost:8091"
  ).replace(/\/$/, "");
}

function getWebEnvConfig() {
  const rootEnv = loadRootEnvFile();
  const arcRpc =
    pick(rootEnv, "NEXT_PUBLIC_ARC_RPC_URL", "ARC_RPC_URL", "ARC_TESTNET_RPC_URL") ??
    "https://rpc.testnet.arc.network";

  return {
    NEXT_PUBLIC_ARC_RPC_URL: arcRpc,
    NEXT_PUBLIC_REGISTRY_ADDRESS:
      pick(rootEnv, "NEXT_PUBLIC_REGISTRY_ADDRESS", "ARC_REGISTRY_ADDRESS") ?? "",
    NEXT_PUBLIC_ENS_RPC_URL:
      pick(rootEnv, "NEXT_PUBLIC_ENS_RPC_URL", "ENS_RPC_URL") ??
      "https://ethereum-sepolia-rpc.publicnode.com",
    NEXT_PUBLIC_WALRUS_AGGREGATOR_URL:
      pick(rootEnv, "NEXT_PUBLIC_WALRUS_AGGREGATOR_URL", "WALRUS_AGGREGATOR_URL") ??
      "https://aggregator.walrus-testnet.walrus.space",
    ARC_RPC_URL: arcRpc,
    ARC_REGISTRY_ADDRESS:
      pick(rootEnv, "NEXT_PUBLIC_REGISTRY_ADDRESS", "ARC_REGISTRY_ADDRESS") ?? "",
    ARC_TESTNET_RPC_URL: pick(rootEnv, "ARC_TESTNET_RPC_URL") ?? arcRpc,
    ENS_RPC_URL:
      pick(rootEnv, "NEXT_PUBLIC_ENS_RPC_URL", "ENS_RPC_URL") ??
      "https://ethereum-sepolia-rpc.publicnode.com",
    WALRUS_AGGREGATOR_URL:
      pick(rootEnv, "NEXT_PUBLIC_WALRUS_AGGREGATOR_URL", "WALRUS_AGGREGATOR_URL") ??
      "https://aggregator.walrus-testnet.walrus.space",
    MARKETPLACE_URL: marketplaceUrl(rootEnv),
    EVAL_RUNNER_URL: evalRunnerUrl(rootEnv),
    EVAL_RUNNER_HOST: pick(rootEnv, "EVAL_RUNNER_HOST") ?? "127.0.0.1",
    EVAL_RUNNER_PORT: pick(rootEnv, "EVAL_RUNNER_PORT") ?? "8090",
  };
}

module.exports = { getWebEnvConfig, loadRootEnvFile };
