import React from "react";
import { Box } from "ink";

import type { ThemeColors } from "../shared-loader.js";
import { MarkdownBlock } from "./MarkdownBlock.js";

interface Props {
  content: string;
  theme: ThemeColors;
}

export const WelcomeBanner: React.FC<Props> = ({ content, theme }) => {
  return (
    <Box flexDirection="column" marginBottom={1}>
      <MarkdownBlock content={content} theme={theme} />
    </Box>
  );
};
