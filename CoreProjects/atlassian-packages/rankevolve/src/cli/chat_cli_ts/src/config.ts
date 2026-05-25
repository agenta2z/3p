import { readFileSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";

import { parse as parseYaml } from "yaml";

export interface UIConfig {
  panel_width: number | null;
  show_tokens: boolean;
  show_timing: boolean;
  streaming_refresh_hz: number;
}

export interface AppConfig {
  provider: "anthropic" | "openai" | "plugboard";
  model: string;
  api_key_env: string | null;
  base_url: string | null;
  max_tokens: number;
  temperature: number;
  system_prompt_file: string;
  theme: string;
  pipeline: string;
  model_pipeline_overrides: Record<string, string>;
  ui: UIConfig;
}

export function getSharedDir(): string {
  const thisDir = dirname(fileURLToPath(import.meta.url));
  return resolve(thisDir, "..", "..", "cli_shared");
}

export function loadConfig(overrides?: Partial<AppConfig>): AppConfig {
  const sharedDir = getSharedDir();
  const defaultYaml = readFileSync(
    resolve(sharedDir, "config", "default-config.yaml"),
    "utf-8",
  );
  const defaults = parseYaml(defaultYaml) as AppConfig;

  const config: AppConfig = {
    ...defaults,
    ui: { ...defaults.ui },
    ...overrides,
  };

  // Auto-switch API key env when switching providers
  if (
    overrides?.provider === "openai" &&
    config.api_key_env === "ANTHROPIC_API_KEY"
  ) {
    config.api_key_env = "OPENAI_API_KEY";
  }
  if (overrides?.provider === "plugboard") {
    config.api_key_env = null;
  }

  return config;
}

export function getApiKey(config: AppConfig): string {
  if (config.provider === "plugboard") {
    return ""; // Plugboard uses CAT/mTLS auth, no API key needed
  }
  const envVar = config.api_key_env;
  if (!envVar) {
    throw new Error(
      `API key env var not configured for provider "${config.provider}".`,
    );
  }
  const key = process.env[envVar];
  if (!key) {
    throw new Error(
      `API key not found. Set the ${envVar} environment variable.`,
    );
  }
  return key;
}
