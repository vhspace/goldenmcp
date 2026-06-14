"use client";

import { useCallback, useRef, useState } from "react";
import { ChatMarkdown } from "@/components/ChatMarkdown";
import { DEMO_PROMPTS } from "@/lib/intent";
import { parseSseChunk, type SseEvent } from "@/lib/chat-sse";

interface ChatMessage {
  role: "user" | "assistant";
  content: string;
  toolEvents?: SseEvent[];
}

function ToolResultCard({ events }: { events: SseEvent[] }) {
  const ends = events.filter((e) => e.event === "tool_end");
  if (ends.length === 0) return null;

  return (
    <div
      style={{
        marginTop: "0.75rem",
        padding: "0.75rem",
        background: "#0d1117",
        border: "1px solid #30363d",
        borderRadius: "8px",
        fontSize: "0.8rem",
      }}
    >
      {ends.map((te, i) => {
        let parsed: Record<string, unknown> = {};
        try {
          parsed = JSON.parse(String(te.data.result ?? "{}")) as Record<string, unknown>;
        } catch {
          parsed = { raw: te.data.result };
        }
        const results = parsed.results as
          | Array<{ ens_name?: string; mcp_endpoint?: string; composite?: number }>
          | undefined;
        const best = results?.[0];
        return (
          <div key={i} style={{ marginBottom: i < ends.length - 1 ? "0.5rem" : 0 }}>
            <strong style={{ color: "#8b949e" }}>{String(te.data.name)}</strong>
            {best && (
              <ul style={{ margin: "0.35rem 0 0", paddingLeft: "1.1rem", color: "#c9d1d9" }}>
                <li>ENS: {best.ens_name}</li>
                <li>Endpoint: {best.mcp_endpoint}</li>
                <li>Composite: {best.composite?.toFixed(3)}</li>
              </ul>
            )}
            {parsed.transaction != null && (
              <p style={{ margin: "0.35rem 0 0", color: "#58a6ff" }}>
                Settlement:{" "}
                <a
                  href={String(parsed.transaction)}
                  target="_blank"
                  rel="noreferrer"
                  style={{ color: "#58a6ff" }}
                >
                  {String(parsed.transaction)}
                </a>
              </p>
            )}
            {parsed.error != null && (
              <p style={{ margin: "0.35rem 0 0", color: "#f85149" }}>{String(parsed.error)}</p>
            )}
          </div>
        );
      })}
    </div>
  );
}

export function ChatConcierge() {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const bufferRef = useRef("");

  const sendMessage = useCallback(
    async (text: string) => {
      const trimmed = text.trim();
      if (!trimmed || loading) return;

      setError("");
      setLoading(true);
      bufferRef.current = "";

      const history = messages.map((m) => ({ role: m.role, content: m.content }));
      setMessages((prev) => [...prev, { role: "user", content: trimmed }]);
      setInput("");

      let assistantText = "";
      const toolEvents: SseEvent[] = [];

      try {
        const res = await fetch("/api/agent/chat", {
          method: "POST",
          headers: { "Content-Type": "application/json", Accept: "text/event-stream" },
          body: JSON.stringify({ message: trimmed, history }),
        });

        if (!res.ok) {
          const errBody = await res.json().catch(() => ({}));
          throw new Error(
            (errBody as { error?: string }).error ?? `Chat failed: HTTP ${res.status}`,
          );
        }

        const reader = res.body?.getReader();
        if (!reader) throw new Error("No response stream from /api/agent/chat");

        const decoder = new TextDecoder();
        while (true) {
          const { done, value } = await reader.read();
          if (done) break;
          bufferRef.current += decoder.decode(value, { stream: true });
          const parsed = parseSseChunk(bufferRef.current);
          bufferRef.current = "";

          for (const ev of parsed) {
            if (ev.event === "token" && typeof ev.data.text === "string") {
              assistantText += ev.data.text;
              setMessages((prev) => {
                const next = [...prev];
                const last = next[next.length - 1];
                if (last?.role === "assistant") {
                  next[next.length - 1] = {
                    ...last,
                    content: assistantText,
                    toolEvents,
                  };
                } else {
                  next.push({ role: "assistant", content: assistantText, toolEvents });
                }
                return next;
              });
            } else if (ev.event === "tool_start" || ev.event === "tool_end" || ev.event === "error") {
              toolEvents.push(ev);
            }
          }
        }

        if (!assistantText && toolEvents.length > 0) {
          setMessages((prev) => [
            ...prev,
            { role: "assistant", content: "(tool calls completed)", toolEvents },
          ]);
        } else if (!assistantText) {
          setMessages((prev) => [
            ...prev,
            { role: "assistant", content: "(empty response)", toolEvents },
          ]);
        }
      } catch (err) {
        const msg = err instanceof Error ? err.message : String(err);
        setError(msg);
      } finally {
        setLoading(false);
      }
    },
    [loading, messages],
  );

  return (
    <section
      style={{
        marginBottom: "2rem",
        padding: "1.25rem",
        background: "#111",
        border: "1px solid #333",
        borderRadius: "10px",
      }}
    >
      <h2 style={{ margin: "0 0 0.5rem", fontSize: "1.35rem" }}>GoldenMCP Concierge</h2>
      <p style={{ color: "#888", margin: "0 0 1rem", fontSize: "0.9rem" }}>
        Natural-language MCP discovery — paid marketplace lookup via x402 USDC on Arc.
      </p>

      <div
        style={{
          display: "flex",
          flexWrap: "wrap",
          gap: "0.5rem",
          marginBottom: "1rem",
        }}
      >
        {DEMO_PROMPTS.map((p) => (
          <button
            key={p.id}
            type="button"
            disabled={loading}
            onClick={() => sendMessage(p.text)}
            style={{
              padding: "0.35rem 0.65rem",
              fontSize: "0.75rem",
              background: "#1a1a2e",
              border: "1px solid #444",
              borderRadius: "6px",
              color: "#ccc",
              cursor: loading ? "not-allowed" : "pointer",
            }}
          >
            {p.id}
          </button>
        ))}
      </div>

      <div
        style={{
          minHeight: "12rem",
          maxHeight: "24rem",
          overflowY: "auto",
          padding: "1rem",
          background: "#0a0a0f",
          borderRadius: "8px",
          border: "1px solid #222",
          marginBottom: "1rem",
        }}
      >
        {messages.length === 0 && (
          <p style={{ color: "#666", margin: 0 }}>Ask for a quote, route, or swap MCP…</p>
        )}
        {messages.map((m, i) => (
          <div key={i} style={{ marginBottom: "1rem" }}>
            <div
              style={{
                fontSize: "0.7rem",
                color: "#666",
                marginBottom: "0.25rem",
                textTransform: "uppercase",
              }}
            >
              {m.role}
            </div>
            {m.role === "assistant" ? (
              <ChatMarkdown content={m.content} />
            ) : (
              <div style={{ color: "#e6e6e6", whiteSpace: "pre-wrap" }}>{m.content}</div>
            )}
            {m.toolEvents && m.toolEvents.length > 0 && <ToolResultCard events={m.toolEvents} />}
          </div>
        ))}
        {loading && <p style={{ color: "#888", margin: 0 }}>Thinking…</p>}
      </div>

      {error && (
        <p style={{ color: "#f87171", fontSize: "0.85rem", margin: "0 0 0.75rem" }}>{error}</p>
      )}

      <form
        onSubmit={(e) => {
          e.preventDefault();
          void sendMessage(input);
        }}
        style={{ display: "flex", gap: "0.5rem" }}
      >
        <input
          type="text"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          placeholder="Find the best quote MCP with reliability ≥ 0.9"
          disabled={loading}
          style={{
            flex: 1,
            padding: "0.65rem 0.85rem",
            background: "#0d0d14",
            border: "1px solid #3b3b50",
            borderRadius: "8px",
            color: "#eee",
          }}
        />
        <button
          type="submit"
          disabled={loading || !input.trim()}
          style={{
            padding: "0.65rem 1.25rem",
            background: loading ? "#333" : "#2563eb",
            border: "none",
            borderRadius: "8px",
            color: "#fff",
            cursor: loading ? "not-allowed" : "pointer",
          }}
        >
          Send
        </button>
      </form>
    </section>
  );
}
