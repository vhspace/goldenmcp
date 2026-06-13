import { CronCapability, HTTPClient, handler, ok, Runner, text, type Runtime } from "@chainlink/cre-sdk";
import { runPipeline } from "./pipeline";
import type { Config } from "./types";

const httpClient = new HTTPClient();

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
  const items = benchmarks.benchmarks ?? [];
  runtime.log(`Found ${items.length} benchmarks`);

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

export { runPipeline };
