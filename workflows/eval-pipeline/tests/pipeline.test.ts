import { describe, expect, test } from "bun:test";
import {
  bytesToBase64,
  bytesToHex,
  finalizeCaiPollStatus,
  finalizeEvalRunPollStatus,
  isCaiConfigured,
  parseCaiAttestation,
  requireCaiAttestationFields,
  scoreToBps,
  shouldSkipCai,
} from "../src/pipeline";

describe("scoreToBps", () => {
  test("converts 0.875 to 8750", () => {
    expect(scoreToBps(0.875)).toBe(8750);
  });

  test("clamps below zero to 0", () => {
    expect(scoreToBps(-0.5)).toBe(0);
  });

  test("clamps above one to 10000", () => {
    expect(scoreToBps(1.5)).toBe(10000);
  });

  test("handles zero and one", () => {
    expect(scoreToBps(0)).toBe(0);
    expect(scoreToBps(1)).toBe(10000);
  });
});

describe("CAI skip / fail logic", () => {
  test("skips CAI when no URL and no secret", () => {
    expect(
      shouldSkipCai(
        {
          chainlinkCaiUrl: "",
        } as Parameters<typeof shouldSkipCai>[0],
        undefined,
      ),
    ).toBe(true);
    expect(isCaiConfigured({ chainlinkCaiUrl: "" } as Parameters<typeof isCaiConfigured>[0], "")).toBe(
      false,
    );
  });

  test("does not skip CAI when URL configured", () => {
    expect(
      shouldSkipCai(
        {
          chainlinkCaiUrl: "https://confidential-ai-dev-preview.cldev.cloud",
        } as Parameters<typeof shouldSkipCai>[0],
        undefined,
      ),
    ).toBe(false);
  });

  test("does not skip CAI when secret present", () => {
    expect(
      shouldSkipCai({ chainlinkCaiUrl: "" } as Parameters<typeof shouldSkipCai>[0], "secret-key"),
    ).toBe(false);
  });

  test("throws when CAI poll returns failed", () => {
    expect(() => finalizeCaiPollStatus("failed", "model error")).toThrow(/CAI inference failed/);
  });

  test("throws when CAI poll ends incomplete", () => {
    expect(() => finalizeCaiPollStatus("processing")).toThrow(/did not complete/);
  });
});

describe("parseCaiAttestation", () => {
  test("builds attestation from a completed CAI status object", () => {
    const status = {
      id: "019ea785-abc",
      status: "completed",
      model: "gemma4",
      output: "PASS — scores are internally consistent.",
      completed_at: "2026-06-07T17:27:43Z",
      usage: { prompt_tokens: 1898, completion_tokens: 1531 },
    };
    const att = parseCaiAttestation(status);
    expect(att).toMatchObject({
      inference_id: "019ea785-abc",
      model: "gemma4",
      verdict: "PASS — scores are internally consistent.",
      completed_at: "2026-06-07T17:27:43Z",
      prompt_tokens: 1898,
      completion_tokens: 1531,
    });
    // No response_digest in the status → sha256(output) fallback transcript hash.
    expect(att.transcript_hash).toMatch(/^0x[0-9a-f]{64}$/);
  });

  test("uses the resource response_digest as the transcript hash", () => {
    const att = parseCaiAttestation({
      id: "019ea31f-0563",
      status: "completed",
      output: "```json\n{\"approved\":true}\n```",
      resources: [
        { response_digest: "0a0124911560a2236e432d30c3e2a90b0666f4c84b40bf10ba01960595c6ecea" },
      ],
    });
    expect(att.transcript_hash).toBe(
      "0x0a0124911560a2236e432d30c3e2a90b0666f4c84b40bf10ba01960595c6ecea",
    );
  });

  test("empty output yields valid attestation, no transcript hash", () => {
    const att = parseCaiAttestation({ id: "inf-1", status: "completed" });
    expect(att.inference_id).toBe("inf-1");
    expect(att.verdict).toBe("");
    expect(att.model).toBe("gemma4");
    expect(att.transcript_hash).toBeUndefined();
  });

  test("requireCaiAttestationFields throws when inference id missing", () => {
    expect(() => requireCaiAttestationFields({ inference_id: "", model: "gemma4", verdict: "" })).toThrow(
      /no inference id/,
    );
    expect(() =>
      requireCaiAttestationFields({ inference_id: "  ", model: "gemma4", verdict: "" }),
    ).toThrow(/no inference id/);
  });

  test("requireCaiAttestationFields accepts a present inference id", () => {
    const att = { inference_id: "inf-1", model: "gemma4", verdict: "PASS" };
    expect(requireCaiAttestationFields(att)).toEqual(att);
  });
});

describe("WASM-safe encoders", () => {
  test("bytesToBase64 matches known vectors", () => {
    const enc = (s: string) => bytesToBase64(new TextEncoder().encode(s));
    expect(enc("")).toBe("");
    expect(enc("f")).toBe("Zg==");
    expect(enc("fo")).toBe("Zm8=");
    expect(enc("foo")).toBe("Zm9v");
    expect(enc("foobar")).toBe("Zm9vYmFy");
    expect(enc('{"run_id":"abc"}')).toBe("eyJydW5faWQiOiJhYmMifQ==");
  });

  test("bytesToHex lowercases and zero-pads", () => {
    expect(bytesToHex(new Uint8Array([0, 15, 255, 16]))).toBe("000fff10");
    expect(bytesToHex(new Uint8Array([]))).toBe("");
  });
});

describe("finalizeEvalRunPollStatus", () => {
  test("throws when eval run failed", () => {
    expect(() => finalizeEvalRunPollStatus("failed", "scored", "inspect timeout")).toThrow(
      /eval run failed/,
    );
  });

  test("throws when eval run ends incomplete", () => {
    expect(() => finalizeEvalRunPollStatus("running", "scored")).toThrow(/did not reach scored/);
    expect(() => finalizeEvalRunPollStatus("publishing", "published")).toThrow(
      /did not reach published/,
    );
  });

  test("does not throw when target status reached", () => {
    expect(() => finalizeEvalRunPollStatus("scored", "scored")).not.toThrow();
    expect(() => finalizeEvalRunPollStatus("published", "published")).not.toThrow();
  });
});
