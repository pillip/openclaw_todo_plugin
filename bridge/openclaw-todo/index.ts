/**
 * OpenClaw bridge plugin — forwards /todo commands to the Python HTTP server.
 *
 * Uses Node built-in `fetch` (Node 18+). Zero npm runtime dependencies.
 *
 * URL resolution order:
 *   1. Plugin config `serverUrl` (from openclaw.plugin.json / gateway config)
 *   2. Environment variable `OPENCLAW_TODO_URL`
 *   3. Default: http://127.0.0.1:8200
 */

const DEFAULT_URL = "http://127.0.0.1:8200";

interface PluginResponse {
  response: string | null;
}

function resolveServerUrl(config?: { serverUrl?: string }): {
  url: string;
  source: "config" | "env" | "default";
} {
  if (config?.serverUrl) {
    return { url: config.serverUrl, source: "config" };
  }
  if (process.env.OPENCLAW_TODO_URL) {
    return { url: process.env.OPENCLAW_TODO_URL, source: "env" };
  }
  return { url: DEFAULT_URL, source: "default" };
}

export default {
  id: "openclaw-todo",
  name: "OpenClaw TODO",

  register(api: any) {
    const { url: todoUrl, source } = resolveServerUrl(api.config);
    api.logger?.info?.(`server URL: ${todoUrl} (source: ${source})`);

    api.registerCommand({
      name: "todo",
      description: "Manage tasks — add, list, board, move, done, drop, edit, project",
      acceptsArgs: true,
      handler: async (ctx: any) => {
        // (A) Use ctx.args — gateway already strips the "/todo" prefix.
        //     ctx.commandBody contains the full normalized body (e.g. "/todo add ...")
        //     which would cause a double-prefix when prepended with "/todo".
        const text = `/todo ${ctx.args ?? ""}`.trim();
        // (D) Prefer senderId, fall back to ctx.from (channel-scoped sender id),
        //     not ctx.channel which is just a surface name like "slack".
        const senderId = ctx.senderId ?? ctx.from ?? "unknown";

        try {
          const res = await fetch(`${todoUrl}/message`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ text, sender_id: senderId }),
          });

          if (!res.ok) {
            // (C) Do not leak internal error details to the user.
            return {
              text: `⚠️ TODO server returned an error (${res.status}). Please try again later.`,
            };
          }

          const data: PluginResponse = await res.json();
          return { text: data.response ?? "No response from TODO server." };
        } catch (err) {
          // (E) Handle network errors (server down, timeout, DNS failure, etc.)
          api.logger?.error?.(`fetch failed: ${err instanceof Error ? err.message : String(err)}`);
          return {
            text: "⚠️ Could not reach the TODO server. Is it running?",
          };
        }
      },
    });
  },
};
