import React from "react";
import { Box, Text } from "ink";

import type { ThemeColors } from "../shared-loader.js";

interface Props {
  content: string;
  theme: ThemeColors;
}

/**
 * MVP markdown renderer: parses line-by-line and applies basic formatting.
 * Phase 2: integrate `marked` with a custom Ink renderer for full markdown support.
 */
export const MarkdownBlock: React.FC<Props> = ({ content, theme }) => {
  const lines = content.split("\n");
  let inCodeBlock = false;

  return (
    <Box flexDirection="column">
      {lines.map((line, i) => {
        // Toggle code block state
        if (line.startsWith("```")) {
          inCodeBlock = !inCodeBlock;
          return (
            <Text key={i} dimColor>
              {line}
            </Text>
          );
        }

        // Inside code block: render as-is with dim styling
        if (inCodeBlock) {
          return (
            <Text key={i} color="#a0a0a0">
              {line}
            </Text>
          );
        }

        // H1
        if (line.startsWith("# ")) {
          return (
            <Text key={i} bold color={theme.assistant_panel_title}>
              {line.slice(2)}
            </Text>
          );
        }

        // H2
        if (line.startsWith("## ")) {
          return (
            <Text key={i} bold color={theme.assistant_panel_title}>
              {line.slice(3)}
            </Text>
          );
        }

        // H3
        if (line.startsWith("### ")) {
          return (
            <Text key={i} bold>
              {line.slice(4)}
            </Text>
          );
        }

        // Unordered list items
        if (line.match(/^\s*[-*]\s/)) {
          const indent = line.match(/^(\s*)/)?.[1] ?? "";
          const text = line.replace(/^\s*[-*]\s/, "");
          return (
            <Text key={i}>
              {indent}{"  \u2022 "}
              {text}
            </Text>
          );
        }

        // Bold text (simple: whole line bold)
        if (line.startsWith("**") && line.endsWith("**")) {
          return (
            <Text key={i} bold>
              {line.slice(2, -2)}
            </Text>
          );
        }

        // Empty line
        if (line.trim() === "") {
          return <Text key={i}>{" "}</Text>;
        }

        // Default: plain text
        return <Text key={i}>{line}</Text>;
      })}
    </Box>
  );
};
