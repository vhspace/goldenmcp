import { existsSync, readFileSync } from "fs";
import { resolve } from "path";
import { defineConfig } from "@playwright/test";

const port = 3099;

const ENV_KEYS = [
  "NEXT_PUBLIC_ARC_RPC_URL",
  "NEXT_PUBLIC_REGISTRY_ADDRESS",
  "NEXT_PUBLIC_WALRUS_AGGREGATOR_URL",
  "NEXT_PUBLIC_ENS_RPC_URL",
  "MARKETPLACE_URL",
] as const;

function loadEnvFile(filePath: string) {
  if (!existsSync(filePath)) return;
  for (const line of readFileSync(filePath, "utf8").split("\n")) {
    const trimmed = line.trim();
    if (!trimmed || trimmed.startsWith("#")) continue;
    const eq = trimmed.indexOf("=");
    if (eq === -1) continue;
    const key = trimmed.slice(0, eq);
    const value = trimmed.slice(eq + 1);
    if (!(key in process.env)) process.env[key] = value;
  }
}

loadEnvFile(resolve(__dirname, "../../.env"));
loadEnvFile(resolve(__dirname, "../../../../.env"));

const webEnv: Record<string, string> = { PORT: String(port) };
for (const key of ENV_KEYS) {
  const value = process.env[key];
  if (value) webEnv[key] = value;
}

export default defineConfig({
  testDir: "./e2e",
  fullyParallel: true,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 1 : 0,
  workers: process.env.CI ? 1 : undefined,
  reporter: process.env.CI ? "github" : "list",
  use: {
    baseURL: `http://localhost:${port}`,
    trace: "on-first-retry",
  },
  webServer: {
    command: "bun run build && bun run start",
    url: `http://localhost:${port}`,
    reuseExistingServer: false,
    timeout: 180_000,
    env: webEnv,
  },
});
