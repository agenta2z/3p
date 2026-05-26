#!/usr/bin/env npx tsx
/**
 * Thin CLI bridge for Slack Web API — called by Python via subprocess.
 *
 * Usage:
 *   npx tsx slack_bridge.ts '{"method":"chat.postMessage","params":{"channel":"C123","text":"Hello"}}'
 *
 * Or via stdin:
 *   echo '{"method":"reactions.add","params":{"channel":"C123","timestamp":"1712023032.1234","name":"white_check_mark"}}' | npx tsx slack_bridge.ts
 *
 * Env:
 *   SLACK_BOT_TOKEN  — required (xoxb-*)
 *
 * Output:
 *   JSON on stdout  — Slack API response
 *   Errors on stderr — JSON { "ok": false, "error": "..." }
 */

import { WebClient } from "@slack/web-api";

async function main() {
  const token = process.env.SLACK_BOT_TOKEN;
  if (!token) {
    console.error(JSON.stringify({ ok: false, error: "SLACK_BOT_TOKEN env var is required" }));
    process.exit(1);
  }

  // Read input from arg or stdin
  let rawInput: string;
  if (process.argv[2]) {
    rawInput = process.argv[2];
  } else {
    // Read from stdin
    const chunks: Buffer[] = [];
    for await (const chunk of process.stdin) {
      chunks.push(chunk);
    }
    rawInput = Buffer.concat(chunks).toString("utf-8").trim();
  }

  if (!rawInput) {
    console.error(JSON.stringify({ ok: false, error: "No input provided. Pass JSON as arg or via stdin." }));
    process.exit(1);
  }

  let input: { method: string; params?: Record<string, unknown> };
  try {
    input = JSON.parse(rawInput);
  } catch {
    console.error(JSON.stringify({ ok: false, error: `Invalid JSON input: ${rawInput.slice(0, 100)}` }));
    process.exit(1);
  }

  if (!input.method) {
    console.error(JSON.stringify({ ok: false, error: "Missing 'method' in input JSON" }));
    process.exit(1);
  }

  const client = new WebClient(token);

  try {
    const result = await client.apiCall(input.method, input.params || {});
    console.log(JSON.stringify(result));
  } catch (e: unknown) {
    const msg = e instanceof Error ? e.message : String(e);
    console.error(JSON.stringify({ ok: false, error: msg, method: input.method }));
    process.exit(1);
  }
}

main();
