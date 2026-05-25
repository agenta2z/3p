import React from "react";
import { Box, Text } from "ink";

import type { DualAgentState } from "../hooks/useDualAgent.js";
import type { ThemeColors } from "../shared-loader.js";
import { MarkdownBlock } from "./MarkdownBlock.js";
import { ThinkingSpinner } from "./Spinner.js";

interface Props {
  state: DualAgentState;
  theme: ThemeColors;
}

export const DualAgentPanel: React.FC<Props> = ({ state, theme }) => {
  return (
    <Box flexDirection="column" marginBottom={1}>
      {/* Header */}
      <Box marginBottom={0}>
        <Text bold color="cyan">
          Dual Agent
        </Text>
        {state.currentPhase && (
          <Text dimColor>
            {" "}| {state.currentPhase} | {state.currentAgent}
          </Text>
        )}
      </Box>

      {/* Completed phases */}
      {state.phases.map((p, i) => (
        <Box
          key={`${p.phase}-${i}`}
          flexDirection="column"
          borderStyle="round"
          borderColor="gray"
          paddingX={1}
          marginBottom={0}
        >
          <Box>
            <Text color="green" bold>
              {"✓ "}
            </Text>
            <Text dimColor>
              {p.phase} ({p.agent_id})
            </Text>
          </Box>
          <MarkdownBlock content={p.content} theme={theme} />
        </Box>
      ))}

      {/* Current streaming phase */}
      {state.isRunning && state.streamingContent && (
        <Box
          flexDirection="column"
          borderStyle="round"
          borderColor={theme.assistant_panel_border}
          paddingX={1}
        >
          <Box marginBottom={0}>
            <Text bold color={theme.assistant_panel_border}>
              {state.currentPhase ?? "Working"} ({state.currentAgent ?? "..."})
            </Text>
          </Box>
          <MarkdownBlock content={state.streamingContent} theme={theme} />
        </Box>
      )}

      {/* Thinking spinner (before first token of current phase) */}
      {state.isRunning && !state.streamingContent && (
        <ThinkingSpinner color={theme.spinner} />
      )}

      {/* Error display */}
      {state.error && (
        <Text color={theme.error_text}>Dual agent error: {state.error}</Text>
      )}
    </Box>
  );
};
