/**
 * OpenClaw bridge plugin — forwards todo: messages to the Python HTTP server.
 *
 * Uses Node built-in `fetch` (Node 18+). Zero npm runtime dependencies.
 *
 * Environment:
 *   OPENCLAW_TODO_URL  Base URL of the Python server (default http://127.0.0.1:8200)
 */

const TODO_URL = process.env.OPENCLAW_TODO_URL ?? "http://127.0.0.1:8200";

interface PluginResponse {
  response: string | null;
}

export default function activate(api: any) {
  api.registerMessageHandler({
    pattern: /^todo:\s*/,
    handler: async (message: any, context: any) => {
      const text = message.text;
      const senderId = context.sender_id ?? context.userId ?? message.user;

      const res = await fetch(`${TODO_URL}/message`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ text, sender_id: senderId }),
      });

      if (!res.ok) {
        const errorBody = await res.text();
        throw new Error(
          `openclaw-todo server error: ${res.status} ${errorBody}`,
        );
      }

      const data: PluginResponse = await res.json();
      if (data.response) {
        return { text: data.response };
      }
      return null;
    },
  });
}
