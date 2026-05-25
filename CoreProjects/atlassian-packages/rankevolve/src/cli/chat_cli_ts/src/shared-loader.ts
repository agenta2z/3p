import { readFileSync } from "node:fs";
import { resolve } from "node:path";

import { getSharedDir } from "./config.js";

export function loadSystemPrompt(filename: string): string {
  return readFileSync(
    resolve(getSharedDir(), "prompts", filename),
    "utf-8",
  );
}

export function loadWelcomeMessage(): string {
  return readFileSync(
    resolve(getSharedDir(), "prompts", "welcome.md"),
    "utf-8",
  );
}

export interface ThemeColors {
  user_panel_border: string;
  user_panel_title: string;
  assistant_panel_border: string;
  assistant_panel_title: string;
  error_text: string;
  spinner: string;
  timestamp: string;
  input_prompt: string;
}

export interface ThemeSymbols {
  user_icon: string;
  assistant_icon: string;
  thinking_spinner: string;
  input_prompt: string;
}

export interface Theme {
  name: string;
  colors: ThemeColors;
  symbols: ThemeSymbols;
}

export function loadTheme(themeName: string): Theme {
  const raw = readFileSync(
    resolve(getSharedDir(), "themes", `${themeName}.json`),
    "utf-8",
  );
  return JSON.parse(raw) as Theme;
}
