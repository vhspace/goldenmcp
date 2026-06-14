const fs = require("fs");
const path = require("path");

/** Parse repo-root .env — bypasses @next/env skipping vars already set to "" in the shell. */
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

const rootEnv = loadRootEnvFile();

const arcRpc =
  rootEnv.NEXT_PUBLIC_ARC_RPC_URL ||
  rootEnv.ARC_RPC_URL ||
  rootEnv.ARC_TESTNET_RPC_URL ||
  "https://rpc.testnet.arc.network";

const registryAddress =
  rootEnv.NEXT_PUBLIC_REGISTRY_ADDRESS || rootEnv.ARC_REGISTRY_ADDRESS || "";

const ensRpc =
  rootEnv.NEXT_PUBLIC_ENS_RPC_URL ||
  rootEnv.ENS_RPC_URL ||
  "https://ethereum-sepolia-rpc.publicnode.com";

const walrusAggregator =
  rootEnv.NEXT_PUBLIC_WALRUS_AGGREGATOR_URL ||
  rootEnv.WALRUS_AGGREGATOR_URL ||
  "https://aggregator.walrus-testnet.walrus.space";

/** @type {import('next').NextConfig} */
const nextConfig = {
  output: "standalone",
  // Injected into process.env for server + client — survives Next's env reset.
  env: {
    NEXT_PUBLIC_ARC_RPC_URL: arcRpc,
    NEXT_PUBLIC_REGISTRY_ADDRESS: registryAddress,
    NEXT_PUBLIC_ENS_RPC_URL: ensRpc,
    NEXT_PUBLIC_WALRUS_AGGREGATOR_URL: walrusAggregator,
    ARC_RPC_URL: arcRpc,
    ARC_REGISTRY_ADDRESS: registryAddress,
    ARC_TESTNET_RPC_URL: rootEnv.ARC_TESTNET_RPC_URL || arcRpc,
    ENS_RPC_URL: ensRpc,
    WALRUS_AGGREGATOR_URL: walrusAggregator,
    MARKETPLACE_URL: rootEnv.MARKETPLACE_URL || "http://localhost:8091",
    EVAL_RUNNER_HOST: rootEnv.EVAL_RUNNER_HOST || "127.0.0.1",
    EVAL_RUNNER_PORT: rootEnv.EVAL_RUNNER_PORT || "8090",
  },
};

module.exports = nextConfig;
