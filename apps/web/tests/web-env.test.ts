import { describe, expect, test, beforeEach, afterEach } from "bun:test";
import {
  arcRpcUrl,
  ensRpcUrl,
  evalRunnerUrl,
  firstEnv,
  marketplaceUrl,
  registryAddress,
  walrusAggregatorUrl,
} from "../src/lib/web-env";

const ORIGINAL_ENV = { ...process.env };

beforeEach(() => {
  process.env = { ...ORIGINAL_ENV };
});

afterEach(() => {
  process.env = { ...ORIGINAL_ENV };
});

describe("web-env (GH #106 Vercel)", () => {
  test("firstEnv prefers first non-empty key", () => {
    process.env.ARC_RPC_URL = "https://arc.example";
    process.env.NEXT_PUBLIC_ARC_RPC_URL = "";
    expect(firstEnv("NEXT_PUBLIC_ARC_RPC_URL", "ARC_RPC_URL")).toBe("https://arc.example");
  });

  test("arcRpcUrl falls back to Arc testnet default", () => {
    delete process.env.NEXT_PUBLIC_ARC_RPC_URL;
    delete process.env.ARC_RPC_URL;
    expect(arcRpcUrl()).toBe("https://rpc.testnet.arc.network");
  });

  test("registryAddress reads NEXT_PUBLIC or ARC alias", () => {
    process.env.ARC_REGISTRY_ADDRESS = "0xregistry";
    expect(registryAddress()).toBe("0xregistry");
  });

  test("evalRunnerUrl prefers EVAL_RUNNER_PUBLIC_URL for production", () => {
    process.env.EVAL_RUNNER_PUBLIC_URL = "https://eval.example.com/";
    expect(evalRunnerUrl()).toBe("https://eval.example.com");
  });

  test("evalRunnerUrl builds from host/port locally", () => {
    delete process.env.EVAL_RUNNER_URL;
    delete process.env.EVAL_RUNNER_PUBLIC_URL;
    process.env.EVAL_RUNNER_HOST = "127.0.0.1";
    process.env.EVAL_RUNNER_PORT = "8090";
    expect(evalRunnerUrl()).toBe("http://127.0.0.1:8090");
  });

  test("marketplaceUrl rejects localhost on Vercel", () => {
    process.env.VERCEL = "1";
    process.env.MARKETPLACE_URL = "http://localhost:8091";
    expect(() => marketplaceUrl()).toThrow(/MARKETPLACE_URL/);
  });

  test("walrusAggregatorUrl has public testnet default", () => {
    delete process.env.NEXT_PUBLIC_WALRUS_AGGREGATOR_URL;
    expect(walrusAggregatorUrl()).toContain("walrus");
  });

  test("ensRpcUrl has Sepolia default", () => {
    delete process.env.NEXT_PUBLIC_ENS_RPC_URL;
    delete process.env.ENS_RPC_URL;
    expect(ensRpcUrl()).toContain("sepolia");
  });
});
