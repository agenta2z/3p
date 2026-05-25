// (c) Meta Platforms, Inc. and affiliates. Confidential and proprietary.

/**
 * Plugboard streaming LLM client for Meta's internal network.
 *
 * Uses Plugboard's direct HTTPS REST proxy (Anthropic Messages API-compatible)
 * at plugboard.x2p.facebook.net/v1/messages. Supports all Plugboard models
 * (Claude, GPT, Gemini, Llama).
 *
 * Auth modes:
 * - Linux (OD/Sandcastle): HTTPS with mTLS client certificate
 * - Mac (laptop): HTTP via x2p proxy at localhost:10054
 *
 * Reference: xplat/vscode/modules/dvsc-core/src/extension-host/plugboard-http-direct/
 */

import * as http from "node:http";
import * as https from "node:https";
import * as fs from "node:fs";
import * as os from "node:os";
import { execFile } from "node:child_process";
import { promisify } from "node:util";

import type { LLMClient, StreamParams } from "./base.js";

const execFileAsync = promisify(execFile);

// ---------------------------------------------------------------------------
// Constants (mirroring dvsc-core/plugboard-http-direct/constants.ts)
// ---------------------------------------------------------------------------

const PLUGBOARD_HOST = "plugboard.x2p.facebook.net";
const DEFAULT_PIPELINE = "usecase-code-devprod";

/** Base64-encoded CAT config for x2p proxy auth (same as dvsc-core) */
const X2P_INJECT_CAT =
  "eyJ2ZXJpZmllciI6ICJtZXRhbWF0ZV9wbGF0Zm9ybS5wbHVnYm9hcmQiLCAidG9rZW5UaW1lb3V0U2Vjb25kcyI6IDMwMCwgImlzTG93Qm94IjogdHJ1ZX0=";

const X2P_PROXY_HOST = "localhost";
const X2P_PROXY_PORT = 10054;

// ---------------------------------------------------------------------------
// Platform detection
// ---------------------------------------------------------------------------

type Platform = "linux" | "mac";

function detectPlatform(): Platform {
  return os.platform() === "darwin" ? "mac" : "linux";
}

// ---------------------------------------------------------------------------
// Certificate handling (Linux mTLS)
// ---------------------------------------------------------------------------

function getDefaultCertPath(): string {
  const username = os.userInfo().username;
  return `/var/facebook/credentials/${username}/agent_x509/3p_ai_tools_${username}.pem`;
}

async function certNeedsRenewal(certPath: string): Promise<boolean> {
  try {
    if (!fs.existsSync(certPath)) {
      return true;
    }
    // Check if cert expires within 24 hours
    await execFileAsync("openssl", [
      "x509",
      "-checkend",
      "86400",
      "-noout",
      "-in",
      certPath,
    ]);
    return false;
  } catch {
    return true;
  }
}

async function refreshCertificate(certPath: string): Promise<boolean> {
  const certDir = certPath.substring(0, certPath.lastIndexOf("/"));
  const certName = certPath
    .substring(certPath.lastIndexOf("/") + 1)
    .replace(/\.pem$/, "");

  try {
    fs.mkdirSync(certDir, { recursive: true });
    await execFileAsync("/usr/bin/certreq", [
      "tls",
      "--mode",
      "user",
      "--dev-env-scope-ids=3p_ai_tools",
      "--combined",
      "--filename",
      certName,
      "--key-dir",
      certDir,
    ]);
    return true;
  } catch {
    return false;
  }
}

async function loadCertificate(): Promise<Buffer | undefined> {
  const certPath =
    process.env.CLAUDE_CODE_CLIENT_CERT ?? getDefaultCertPath();
  const isDefault = !process.env.CLAUDE_CODE_CLIENT_CERT;

  try {
    if (isDefault && (await certNeedsRenewal(certPath))) {
      await refreshCertificate(certPath);
    }
    if (fs.existsSync(certPath)) {
      return fs.readFileSync(certPath);
    }
  } catch {
    // Certificate loading failed — request will proceed without mTLS
  }
  return undefined;
}

// ---------------------------------------------------------------------------
// SSE parsing (simplified from dvsc-core/sse-parser.ts)
// ---------------------------------------------------------------------------

interface SSEEvent {
  type: string;
  delta?: { type: string; text?: string };
  error?: { type?: string; message?: string };
  message?: string;
}

class PlugboardError extends Error {
  constructor(message: string) {
    super(message);
    this.name = "PlugboardError";
  }
}

function parseSSELine(line: string): string | null {
  if (!line.startsWith("data: ")) {
    return null;
  }
  const jsonStr = line.slice(6);
  if (jsonStr === "[DONE]") {
    return null;
  }

  try {
    const event = JSON.parse(jsonStr) as SSEEvent;

    if (event.type === "error" || event.type === "server_error") {
      const msg =
        (typeof event.message === "string" ? event.message : undefined) ??
        event.error?.message ??
        `Plugboard error: ${jsonStr}`;
      throw new PlugboardError(msg);
    }

    if (
      event.type === "content_block_delta" &&
      event.delta?.type === "text_delta" &&
      event.delta.text
    ) {
      return event.delta.text;
    }
  } catch (e) {
    if (e instanceof PlugboardError) {
      throw e;
    }
    // Ignore JSON parse errors for non-critical SSE events
  }

  return null;
}

// ---------------------------------------------------------------------------
// PlugboardClient
// ---------------------------------------------------------------------------

export class PlugboardClient implements LLMClient {
  private pipeline: string;
  private modelPipelineOverrides: Record<string, string>;

  constructor(
    pipeline: string = DEFAULT_PIPELINE,
    modelPipelineOverrides: Record<string, string> = {},
  ) {
    this.pipeline = pipeline;
    this.modelPipelineOverrides = modelPipelineOverrides;
  }

  async *streamResponse(params: StreamParams): AsyncIterable<string> {
    const requestId = `rankevolve_chat_cli_${Date.now()}_${Math.random().toString(36).slice(2, 10)}`;

    const body = JSON.stringify({
      model: params.model,
      max_tokens: params.maxTokens,
      messages: params.messages,
      system: params.system,
      temperature: params.temperature,
      stream: true,
    });

    const override = {
      sub_usecase: requestId,
      pipeline: this.modelPipelineOverrides[params.model] ?? this.pipeline,
    };

    const headers: Record<string, string> = {
      "Content-Type": "application/json",
      "Content-Length": String(Buffer.byteLength(body)),
      "x-x2pagentd-inject-cat": X2P_INJECT_CAT,
      "X-Meta-Request-Id": requestId,
      "x-meta-plugboard-override": Buffer.from(
        JSON.stringify(override),
      ).toString("base64"),
    };

    const platform = detectPlatform();

    // Event queue for bridging callback-based HTTP to async generator
    const eventQueue: string[] = [];
    let resolveWaiting: (() => void) | null = null;
    let streamDone = false;
    let streamError: Error | null = null;

    const pushText = (text: string): void => {
      eventQueue.push(text);
      resolveWaiting?.();
    };

    const handleResponse = (
      res: http.IncomingMessage,
      reject: (err: Error) => void,
    ): void => {
      if (res.statusCode !== 200) {
        const error = new Error(
          `Plugboard HTTP ${String(res.statusCode)}: ${String(res.statusMessage)}`,
        );
        streamError = error;
        reject(error);
        resolveWaiting?.();
        return;
      }

      res.setEncoding("utf8");
      let buffer = "";

      res.on("data", (chunk: string) => {
        buffer += chunk;
        const lines = buffer.split("\n");
        buffer = lines.pop() ?? "";

        for (const line of lines) {
          try {
            const text = parseSSELine(line);
            if (text) {
              pushText(text);
            }
          } catch (e) {
            streamError = e instanceof Error ? e : new Error(String(e));
            resolveWaiting?.();
          }
        }
      });

      res.on("end", () => {
        streamDone = true;
        resolveWaiting?.();
      });

      res.on("error", (err) => {
        streamError = err;
        resolveWaiting?.();
      });
    };

    // Start the HTTP request
    const requestPromise = new Promise<void>((resolve, reject) => {
      const onError = (err: Error): void => {
        streamError = err;
        resolveWaiting?.();
        reject(err);
      };

      if (platform === "mac") {
        // Mac: HTTP via x2p proxy
        const req = http.request(
          {
            hostname: X2P_PROXY_HOST,
            port: X2P_PROXY_PORT,
            path: `http://${PLUGBOARD_HOST}/v1/messages`,
            method: "POST",
            headers: { ...headers, Host: PLUGBOARD_HOST },
          },
          (res) => {
            handleResponse(res, reject);
            res.on("end", resolve);
          },
        );
        req.on("error", onError);
        req.write(body);
        req.end();
      } else {
        // Linux: HTTPS with mTLS
        loadCertificate()
          .then((cert) => {
            const tlsOptions: https.RequestOptions = {
              hostname: PLUGBOARD_HOST,
              port: 443,
              path: "/v1/messages",
              method: "POST",
              headers,
              rejectUnauthorized: true,
            };

            if (cert) {
              tlsOptions.cert = cert;
              tlsOptions.key = cert;
            }

            const req = https.request(tlsOptions, (res) => {
              if (
                (res.statusCode === 401 || res.statusCode === 403) &&
                !cert
              ) {
                const error = new Error(
                  `Authentication failed (HTTP ${String(res.statusCode)}): No mTLS certificate found at ${getDefaultCertPath()}`,
                );
                streamError = error;
                reject(error);
                resolveWaiting?.();
                return;
              }
              handleResponse(res, reject);
              res.on("end", resolve);
            });

            req.on("error", (err) => {
              if (!cert) {
                onError(
                  new Error(
                    `Connection failed: ${err.message}. No mTLS certificate found at ${getDefaultCertPath()}`,
                  ),
                );
              } else {
                onError(err);
              }
            });

            req.write(body);
            req.end();
          })
          .catch(onError);
      }
    });

    // Yield text tokens as they arrive
    try {
      while (!streamDone || eventQueue.length > 0) {
        if (eventQueue.length > 0) {
          const text = eventQueue.shift();
          if (text) {
            yield text;
          }
        } else if (streamError) {
          throw streamError;
        } else if (!streamDone) {
          await new Promise<void>((r) => {
            resolveWaiting = r;
          });
        }
      }
      // Check for error after stream ends
      if (streamError) {
        throw streamError;
      }
    } finally {
      await requestPromise.catch(() => undefined);
    }
  }

  async close(): Promise<void> {
    // No persistent connection to clean up
  }
}
