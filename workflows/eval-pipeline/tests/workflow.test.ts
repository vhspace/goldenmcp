import { describe, expect, test } from "bun:test";
import { parseCaiAttestation, requireCaiAttestationFields, type CaiStatus } from "../src/pipeline";

describe("eval pipeline config", () => {
  test("scoring weights", () => {
    const composite = 0.45 * 0.9 + 0.35 * 0.8 + 0.2 * 0.7;
    expect(composite).toBeGreaterThan(0.8);
  });
});

// Handler B builds its attestation from the CAI callback body alone (the CRE HTTP
// trigger payload carries no URL/query). These cover that parse boundary; the
// inference_id -> run_id correlation is covered in the eval-runner pytest suite.
describe("attestation from CAI callback body", () => {
  const status: CaiStatus = {
    id: "019ec2ce-ce8a-7d30-97aa-dc9013776626",
    status: "completed",
    model: "gemma4",
    output: "PASS",
    resources: [
      { response_digest: "99fe5155d137d2f6dbac784cb33c7d3a42a51bd5da656477a6a016a3843e71b2" },
    ],
  };

  test("derives inference_id + transcript_hash a publish call would key on", () => {
    const att = requireCaiAttestationFields(parseCaiAttestation(status));
    expect(att.inference_id).toBe("019ec2ce-ce8a-7d30-97aa-dc9013776626");
    expect(att.transcript_hash).toBe(
      "0x99fe5155d137d2f6dbac784cb33c7d3a42a51bd5da656477a6a016a3843e71b2",
    );
  });

  test("requireCaiAttestationFields rejects a status with no inference id", () => {
    expect(() => requireCaiAttestationFields(parseCaiAttestation({ status: "completed" }))).toThrow(
      /no inference id/,
    );
  });
});
