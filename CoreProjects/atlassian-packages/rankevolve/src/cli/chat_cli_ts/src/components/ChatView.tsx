import React from "react";
import { Box } from "ink";

import type { ChatMessage } from "../schema.js";
import type { ThemeColors } from "../shared-loader.js";
import { MessagePanel } from "./MessagePanel.js";

interface Props {
  messages: ChatMessage[];
  theme: ThemeColors;
  maxWidth?: number;
}

export const ChatView: React.FC<Props> = ({ messages, theme, maxWidth }) => {
  return (
    <Box flexDirection="column">
      {messages.map((msg) => (
        <MessagePanel
          key={msg.id}
          message={msg}
          theme={theme}
          maxWidth={maxWidth}
        />
      ))}
    </Box>
  );
};
