import { CronCapability, HTTPCapability, handler, Runner, type Runtime } from "@chainlink/cre-sdk";

interface Config {
  schedule: string;
  evalRunnerUrl: string;
  walrusAggregatorUrl: string;
  arcRegistryAddress: string;
  chainlinkCaiUrl: string;
}

interface EvalResult {
  run_id: string;
  manifest: {
    mcp: string;
    capability: string;
    composite: number;
    failed: boolean;
    data_score: number;
    path_score: number;
    token_efficiency: number;
    walrus_manifest_blob_id: string;
  };
  walrus_manifest_blob_id: string;
}

async function onCronTrigger(runtime: Runtime<Config>): Promise<string> {
  const config = runtime.config;
  const http = new HTTPCapability();

  runtime.log.info("GoldenMCP eval pipeline triggered");

  const evalResponse = await http
    .client()
    .sendRequest(runtime, {
      url: `${config.evalRunnerUrl}/benchmarks`,
      method: "GET",
    })
    .result();

  const benchmarks = JSON.parse(evalResponse.bodyText);
  runtime.log.info(`Found ${benchmarks.benchmarks?.length ?? 0} benchmarks`);

  const results: string[] = [];
  for (const bench of benchmarks.benchmarks ?? []) {
    runtime.log.info(`Processing ${bench.mcp}/${bench.capability}`);

    const manifestUrl = `${config.walrusAggregatorUrl}/v1/blobs/latest-${bench.mcp}-${bench.capability}`;
    try {
      const walrusResponse = await http
        .client()
        .sendRequest(runtime, { url: manifestUrl, method: "GET" })
        .result();

      const manifest = JSON.parse(walrusResponse.bodyText);
      runtime.log.info(
        `Score ${bench.mcp}/${bench.capability}: composite=${manifest.composite} failed=${manifest.failed}`,
      );

      if (config.chainlinkCaiUrl) {
        const caiResponse = await http
          .client()
          .sendRequest(runtime, {
            url: config.chainlinkCaiUrl,
            method: "POST",
            body: JSON.stringify({
              eval_summary: manifest,
              mcp: bench.mcp,
              capability: bench.capability,
            }),
            headers: { "Content-Type": "application/json" },
          })
          .result();
        runtime.log.info(`CAI attestation response: ${caiResponse.statusCode}`);
      }

      results.push(`${bench.mcp}/${bench.capability}:${manifest.composite}`);
    } catch (err) {
      runtime.log.error(`Failed ${bench.mcp}/${bench.capability}: ${err}`);
      throw err;
    }
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
