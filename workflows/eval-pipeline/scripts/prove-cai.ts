// Proof harness: hit the LIVE Confidential AI TEE with a real GoldenMCP score
// manifest, poll to completion, then run the PRODUCTION parser
// (parseCaiAttestation) on the real response. Prints the attestation the
// pipeline would record on-chain. Not part of the workflow build.
//
//   CHAINLINK_CAI_API_KEY=... bun run scripts/prove-cai.ts
import { parseCaiAttestation, toBytes32, type CaiStatus } from "../src/pipeline.ts";

const BASE = (process.env.CHAINLINK_CAI_URL?.trim() || "https://confidential-ai-dev-preview.cldev.cloud").replace(/\/$/, "");
const KEY = process.env.CHAINLINK_CAI_API_KEY;
if (!KEY) throw new Error("CHAINLINK_CAI_API_KEY required");

const manifest = {
  schema_version: "goldenmcp/score-manifest/v1",
  mcp: "lifi",
  capability: "quote",
  run_id: "proof-run-1",
  failed: false,
  data_score: 0.92,
  path_score: 0.85,
  token_efficiency: 0.7,
  composite: 0.86,
};
const manifestBase64 = Buffer.from(JSON.stringify(manifest), "utf8").toString("base64");

const auth = { Authorization: `Bearer ${KEY}` };
const log = (...a: unknown[]) => console.log(new Date().toISOString(), ...a);

log(`CAI POST /v1/inference model=gemma4 run_id=${manifest.run_id}`);
const submit = await fetch(`${BASE}/v1/inference`, {
  method: "POST",
  headers: { ...auth, "Content-Type": "application/json" },
  body: JSON.stringify({
    model: "gemma4",
    prompt:
      "You are reviewing a GoldenMCP eval score manifest produced for an MCP server.\n" +
      "Assess whether the scores in manifest.json are internally consistent and the composite is plausible.\n" +
      "Reply with a short verdict: state PASS or FAIL and one sentence of reasoning.",
    resources: [{ filename: "manifest.json", content_type: "application/json", content_base64: manifestBase64 }],
  }),
});
const submitJson = (await submit.json()) as { id?: string; status?: string };
log(`submit -> http=${submit.status} id=${submitJson.id} status=${submitJson.status}`);
const id = submitJson.id;
if (!id) throw new Error(`no inference id: ${JSON.stringify(submitJson)}`);

let status: CaiStatus = {};
for (let attempt = 1; attempt <= 60; attempt++) {
  await new Promise((r) => setTimeout(r, 3000));
  const poll = await fetch(`${BASE}/v1/inference/${encodeURIComponent(id)}`, { headers: auth });
  status = (await poll.json()) as CaiStatus;
  log(`poll ${attempt}/60 -> status=${status.status}`);
  if (status.status === "completed" || status.status === "failed") break;
}

log("=== RAW completed status (the TEE response) ===");
console.log(JSON.stringify(status, null, 2));

log("=== PRODUCTION parseCaiAttestation(status) output ===");
const attestation = parseCaiAttestation(status);
console.log(JSON.stringify(attestation, null, 2));

log("=== correctness checks ===");
const responseDigest = status.resources?.[0]?.response_digest;
console.log("inference_id == status.id:", attestation.inference_id === status.id);
console.log("verdict == status.output:", attestation.verdict === (status.output ?? ""));
console.log("response_digest present:", Boolean(responseDigest), responseDigest ?? "(none)");
console.log(
  "transcript_hash == toBytes32(response_digest):",
  attestation.transcript_hash === toBytes32(responseDigest),
);
console.log("transcript_hash is 0x+64hex:", /^0x[0-9a-f]{64}$/.test(attestation.transcript_hash ?? ""));
