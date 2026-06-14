import { webAgentApiKey, webAgentUrl } from "@/lib/web-env";

export async function POST(request: Request) {
  let body: { message?: string; history?: Array<{ role: string; content: string }> };
  try {
    body = await request.json();
  } catch {
    return new Response(JSON.stringify({ error: "Invalid JSON body" }), {
      status: 400,
      headers: { "Content-Type": "application/json" },
    });
  }

  const message = body.message?.trim();
  if (!message) {
    return new Response(JSON.stringify({ error: "message is required" }), {
      status: 400,
      headers: { "Content-Type": "application/json" },
    });
  }

  const agentUrl = webAgentUrl();
  const chatUrl = `${agentUrl}/chat`;

  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    Accept: "text/event-stream",
  };
  const apiKey = webAgentApiKey();
  if (apiKey) {
    headers.Authorization = `Bearer ${apiKey}`;
  }

  try {
    const upstream = await fetch(chatUrl, {
      method: "POST",
      headers,
      body: JSON.stringify({ message, history: body.history }),
      signal: AbortSignal.timeout(300_000),
    });

    if (!upstream.ok) {
      const text = await upstream.text();
      return new Response(
        JSON.stringify({
          error: `web-agent chat failed: HTTP ${upstream.status} ${text}`,
          web_agent_url: chatUrl,
        }),
        { status: 502, headers: { "Content-Type": "application/json" } },
      );
    }

    if (!upstream.body) {
      return new Response(
        JSON.stringify({ error: "web-agent returned empty body", web_agent_url: chatUrl }),
        { status: 502, headers: { "Content-Type": "application/json" } },
      );
    }

    return new Response(upstream.body, {
      status: 200,
      headers: {
        "Content-Type": "text/event-stream",
        "Cache-Control": "no-cache",
        Connection: "keep-alive",
      },
    });
  } catch (err) {
    const msg = err instanceof Error ? err.message : String(err);
    return new Response(
      JSON.stringify({
        error: `web-agent unreachable at ${chatUrl} — ${msg}. Set WEB_AGENT_URL or WEB_AGENT_PUBLIC_URL.`,
        web_agent_url: chatUrl,
      }),
      { status: 502, headers: { "Content-Type": "application/json" } },
    );
  }
}
