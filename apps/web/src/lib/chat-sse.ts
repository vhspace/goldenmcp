/** Parse SSE chunks from web-agent /api/agent/chat proxy. */

export interface SseEvent {
  event: string;
  data: Record<string, unknown>;
}

export function parseSseChunk(buffer: string): SseEvent[] {
  const events: SseEvent[] = [];
  const blocks = buffer.split("\n\n").filter(Boolean);

  for (const block of blocks) {
    let event = "message";
    let dataRaw = "";
    for (const line of block.split("\n")) {
      if (line.startsWith("event:")) {
        event = line.slice(6).trim();
      } else if (line.startsWith("data:")) {
        dataRaw = line.slice(5).trim();
      }
    }
    if (!dataRaw) continue;
    try {
      events.push({ event, data: JSON.parse(dataRaw) as Record<string, unknown> });
    } catch {
      events.push({ event, data: { raw: dataRaw } });
    }
  }

  return events;
}
