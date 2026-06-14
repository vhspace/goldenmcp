import { describe, expect, test } from "bun:test";
import { parseSseChunk } from "../src/lib/chat-sse";

describe("chat SSE parser", () => {
  test("parseSseChunk extracts event and JSON data", () => {
    const chunk = 'event: token\ndata: {"text":"hello"}\n\n';
    const parsed = parseSseChunk(chunk);
    expect(parsed).toEqual([{ event: "token", data: { text: "hello" } }]);
  });

  test("parseSseChunk handles multiple events", () => {
    const chunk =
      'event: tool_start\ndata: {"name":"lookup_mcp"}\n\nevent: token\ndata: {"text":"x"}\n\n';
    const parsed = parseSseChunk(chunk);
    expect(parsed).toHaveLength(2);
    expect(parsed[0]?.event).toBe("tool_start");
    expect(parsed[1]?.event).toBe("token");
  });
});
