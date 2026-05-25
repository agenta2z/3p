import React from "react";
import { Box, Text } from "ink";
import InkSpinner from "ink-spinner";

interface Props {
  label?: string;
  color?: string;
}

export const ThinkingSpinner: React.FC<Props> = ({
  label = "Thinking...",
  color = "#ffaf00",
}) => (
  <Box>
    <Text color={color}>
      <InkSpinner type="dots" />
    </Text>
    <Text> {label}</Text>
  </Box>
);
