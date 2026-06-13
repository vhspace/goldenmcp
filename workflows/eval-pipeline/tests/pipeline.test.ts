import { describe, expect, test } from "bun:test";
import {
  finalizeCaiPollStatus,
  isCaiConfigured,
  parseCaiAttestation,
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
  test("parses JSON attestation fields from output", () => {
    const output = JSON.stringify({
      attestation_id: "att-123",
      attestation_tx_hash: "0xabc",
      review: "ok",
    });
    expect(parseCaiAttestation(output)).toEqual({
      attestation_id: "att-123",
      attestation_tx_hash: "0xabc",
    });
  });

  test("parses fenced JSON block", () => {
    const output = `Review complete.\n\`\`\`json\n{"attestation_id":"x","attestation_tx_hash":"0xdead"}\n\`\`\``;
    expect(parseCaiAttestation(output)).toEqual({
      attestation_id: "x",
      attestation_tx_hash: "0xdead",
    });
  });
});
