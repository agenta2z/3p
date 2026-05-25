import React from "react";
import { Box, Text } from "ink";

import type { ChatMessage } from "../schema.js";
import type { ThemeColors } from "../shared-loader.js";
import { MarkdownBlock } from "./MarkdownBlock.js";

interface Props {
  message: ChatMessage;
  theme: ThemeColors;
  maxWidth?: number;
}

export const MessagePanel: React.FC<Props> = ({
  message,
  theme,
  maxWidth,
}) => {
  const isUser = message.role === "user";
  const borderColor = isUser
    ? theme.user_panel_border
    : theme.assistant_panel_border;
  const title = isUser ? "You" : "Assistant";

  return (
    <Box
      flexDirection="column"
      borderStyle="round"
      borderColor={borderColor}
      paddingX={1}
      width={maxWidth ?? undefined}
      marginBottom={1}
    >
      <Box marginBottom={0}>
        <Text bold color={borderColor}>
          {title}
        </Text>
      </Box>
      <Box flexDirection="column">
        {isUser ? (
          <Text>{message.content}</Text>
        ) : (
          <MarkdownBlock content={message.content} theme={theme} />
        )}
      </Box>
    </Box>
  );
};
