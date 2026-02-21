/**
 * OpenClaw bridge plugin — forwards /todo messages to the Python HTTP server.
 *
 * Uses Node built-in `fetch` (Node 18+). Zero npm runtime dependencies.
 *
 * Environment:
 *   OPENCLAW_TODO_URL  Base URL of the Python server (default http://127.0.0.1:8200)
 */

const TODO_URL = process.env.OPENCLAW_TODO_URL ?? "http://127.0.0.1:8200";

interface MessageContext {
  sender_id: string;
}

interface PluginResponse {
  response: string | null;
}

export async function handleMessage(
  text: string,
  context: MessageContext,
): Promise<string | null> {
  const url = `${TODO_URL}/message`;

  const res = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ text, sender_id: context.sender_id }),
  });

  if (!res.ok) {
    const errorBody = await res.text();
    throw new Error(
      `openclaw-todo server error: ${res.status} ${errorBody}`,
    );
  }

  const data: PluginResponse = await res.json();
  return data.response;
}
