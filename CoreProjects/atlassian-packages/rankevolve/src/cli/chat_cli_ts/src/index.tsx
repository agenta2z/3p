#!/usr/bin/env npx tsx

import React from "react";
import { render } from "ink";
import { parseArgs } from "node:util";

import { App } from "./App.js";
import { loadConfig, getApiKey } from "./config.js";
import { loadSystemPrompt, loadWelcomeMessage, loadTheme } from "./shared-loader.js";
import { AnthropicClient } from "./llm/anthropic-client.js";
import { OpenAIClient } from "./llm/openai-client.js";
import { PlugboardClient } from "./llm/plugboard-client.js";
import type { LLMClient } from "./llm/base.js";

// Parse CLI arguments
const { values } = parseArgs({
  options: {
    model: { type: "string", short: "m" },
    provider: { type: "string", short: "p" },
    "root-folder": { type: "string", short: "r" },
  },
  strict: false,
});

// Load configuration
const config = loadConfig({
  ...(values.model ? { model: values.model } : {}),
  ...(values.provider
    ? { provider: values.provider as "anthropic" | "openai" | "plugboard" }
    : {}),
});

// Load shared artifacts
const systemPrompt = loadSystemPrompt(config.system_prompt_file);
const welcomeMessage = loadWelcomeMessage();
const theme = loadTheme(config.theme);

// Create LLM client
let client: LLMClient;
if (config.provider === "plugboard") {
  client = new PlugboardClient(config.pipeline, config.model_pipeline_overrides);
} else {
  const apiKey = getApiKey(config);
  if (config.provider === "openai") {
    client = new OpenAIClient(apiKey, config.base_url ?? undefined);
  } else {
    client = new AnthropicClient(apiKey, config.base_url ?? undefined);
  }
}

const rootFolder = (values["root-folder"] as string) ?? process.cwd();

// Render the Ink application
render(
  <App
    client={client}
    config={config}
    systemPrompt={systemPrompt}
    welcomeMessage={welcomeMessage}
    theme={theme}
    rootFolder={rootFolder}
  />,
);
