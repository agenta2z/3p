import React, { useState } from "react";
import { Box, Text } from "ink";
import TextInput from "ink-text-input";

interface Props {
  onSubmit: (text: string) => void;
  promptChar?: string;
  promptColor?: string;
}

export const InputArea: React.FC<Props> = ({
  onSubmit,
  promptChar = "> ",
  promptColor = "#5f87ff",
}) => {
  const [value, setValue] = useState("");

  const handleSubmit = (text: string) => {
    const trimmed = text.trim();
    if (trimmed) {
      onSubmit(trimmed);
    }
    setValue("");
  };

  return (
    <Box>
      <Text color={promptColor}>{promptChar}</Text>
      <TextInput value={value} onChange={setValue} onSubmit={handleSubmit} />
    </Box>
  );
};
