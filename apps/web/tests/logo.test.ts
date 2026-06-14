import { describe, expect, test } from "bun:test";
import { GOLDENMCP_LOGO_PATH } from "../src/components/GoldenMcpLogo";

describe("GoldenMcpLogo", () => {
  test("logo is served from public images", () => {
    expect(GOLDENMCP_LOGO_PATH).toBe("/images/goldenmcp-logo.png");
  });
});
