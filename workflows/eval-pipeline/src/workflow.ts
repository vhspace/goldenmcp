import { CronCapability, HTTPClient, handler, ok, Runner, text, type Runtime } from "@chainlink/cre-sdk";
import { runPipeline } from "./pipeline";
import type { Config } from "./types";

const httpClient = new HTTPClient();

function benchmarkKey(mcp: string, capability: string): string {
  return `${mcp}/${capability}`;
}

function filterBenchmarks(
  config: Config,
  items: Array<{ mcp: string; capability: string }>,
): Array<{ mcp: string; capability: string }> {
  const allowlist = config.benchmarkAllowlist?.filter(Boolean) ?? [];
  if (allowlist.length === 0) {
    return items;
  }
  const allowed = new Set(allowlist);
  return items.filter((bench) => allowed.has(benchmarkKey(bench.mcp, bench.capability)));
}

async function onCronTrigger(runtime: Runtime<Config>): Promise<string> {
  const config = runtime.config;
  runtime.log("GoldenMCP eval pipeline cron triggered");

  const benchmarksResponse = httpClient
    .sendRequest(runtime, {
      url: `${config.evalRunnerUrl.replace(/\/$/, "")}/benchmarks`,
      method: "GET",
    })
    .result();

  if (!ok(benchmarksResponse)) {
    throw new Error(
      `GET /benchmarks failed: HTTP ${benchmarksResponse.statusCode} — ${text(benchmarksResponse)}`,
    );
  }

  const benchmarks = JSON.parse(text(benchmarksResponse)) as {
    benchmarks?: Array<{ mcp: string; capability: string }>;
  };
  const allItems = benchmarks.benchmarks ?? [];
  const items = filterBenchmarks(config, allItems);
  if (items.length !== allItems.length) {
    runtime.log(
      `benchmarkAllowlist active — running ${items.length}/${allItems.length} benchmarks: ${items.map((b) => benchmarkKey(b.mcp, b.capability)).join(", ")}`,
    );
  } else {
    runtime.log(`Found ${items.length} benchmarks`);
  }

  if (config.useScoreOnly && items.length === 0) {
    throw new Error(
      "useScoreOnly=true but no benchmarks matched benchmarkAllowlist — set allowlist e.g. lifi/quote",
    );
  }

  const results: string[] = [];
  for (const bench of items) {
    runtime.log(`Processing ${bench.mcp}/${bench.capability}`);
    const result = await runPipeline(runtime, {
      mcp: bench.mcp,
      capability: bench.capability,
      agentId: config.defaultAgentId,
    });
    results.push(`${bench.mcp}/${bench.capability}:${result.manifest.composite}`);
  }

  return `Pipeline complete: ${results.join(", ")}`;
}

const initWorkflow = (config: Config) => {
  const cron = new CronCapability();
  return [handler(cron.trigger({ schedule: config.schedule }), onCronTrigger)];
};

export async function main() {
  const runner = await Runner.newRunner<Config>();
  await runner.run(initWorkflow);
}
