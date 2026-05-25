import React, { useCallback, useMemo, useRef } from "react";
import { Box, Text, useApp } from "ink";

import type { LLMClient } from "./llm/base.js";
import type { AppConfig } from "./config.js";
import type { Theme } from "./shared-loader.js";
import { ChatView } from "./components/ChatView.js";
import { DualAgentPanel } from "./components/DualAgentPanel.js";
import { InputArea } from "./components/InputArea.js";
import { MessagePanel } from "./components/MessagePanel.js";
import { MarkdownBlock } from "./components/MarkdownBlock.js";
import { ThinkingSpinner } from "./components/Spinner.js";
import { WelcomeBanner } from "./components/WelcomeBanner.js";
import { useChat } from "./hooks/useChat.js";
import { useDualAgent } from "./hooks/useDualAgent.js";
import { useKnowledge } from "./hooks/useKnowledge.js";
import { useStreaming } from "./hooks/useStreaming.js";

interface Props {
  client: LLMClient;
  config: AppConfig;
  systemPrompt: string;
  welcomeMessage: string;
  theme: Theme;
  rootFolder: string;
}

export const App: React.FC<Props> = ({
  client,
  config,
  systemPrompt,
  welcomeMessage,
  theme,
  rootFolder,
}) => {
  const { exit } = useApp();
  const {
    messages,
    isStreaming,
    setIsStreaming,
    streamingContent,
    setStreamingContent,
    error,
    setError,
    addUserMessage,
    addAssistantMessage,
    appendStreamingToken,
    getApiMessages,
    clearMessages,
  } = useChat(systemPrompt);

  const { state: dualAgentState, runDualAgent } = useDualAgent({ rootFolder });
  const {
    state: knowledgeState,
    addKnowledge,
    searchKnowledge,
    listKnowledge,
    clearKnowledge,
  } = useKnowledge();

  const lastTimingRef = useRef<number | null>(null);

  const callbacks = useMemo(
    () => ({
      onToken: (token: string) => {
        appendStreamingToken(token);
      },
      onStart: () => {
        setIsStreaming(true);
        setError(null);
        setStreamingContent("");
        lastTimingRef.current = null;
      },
      onComplete: (fullText: string, startTime: number) => {
        const elapsed = Date.now() - startTime;
        lastTimingRef.current = elapsed;
        setIsStreaming(false);
        addAssistantMessage(fullText, {
          model: config.model,
          duration_ms: elapsed,
        });
      },
      onError: (err: Error) => {
        setIsStreaming(false);
        setError(err.message);
      },
    }),
    [
      appendStreamingToken,
      setIsStreaming,
      setError,
      setStreamingContent,
      addAssistantMessage,
      config.model,
    ],
  );

  const { sendMessage } = useStreaming(
    client,
    config,
    systemPrompt,
    callbacks,
  );

  const handleSubmit = useCallback(
    async (text: string) => {
      // Handle commands
      const lower = text.toLowerCase().trim();
      if (lower === "/exit" || lower === "/quit") {
        exit();
        return;
      }
      if (lower === "/clear") {
        clearMessages();
        return;
      }
      if (lower.startsWith("/model ")) {
        config.model = text.split(" ", 2)[1]!.trim();
        return;
      }
      if (lower.startsWith("/code ")) {
        const request = text.slice(6).trim();
        if (request) {
          runDualAgent(request);
        }
        return;
      }
      if (lower === "/code") {
        return; // No request provided, ignore
      }
      if (lower.startsWith("/kn")) {
        const args = text.slice(3).trim();
        const parts = args.split(" ");
        const subcmd = parts[0] ?? "";
        const rest = parts.slice(1).join(" ");

        if (subcmd === "add" && rest) {
          addKnowledge(rest);
        } else if (subcmd === "search" && rest) {
          searchKnowledge(rest);
        } else if (subcmd === "list") {
          listKnowledge();
        } else if (subcmd === "clear") {
          clearKnowledge();
        } else if (args) {
          // Backward compat: "/kn <text>" = "/kn add <text>"
          addKnowledge(args);
        }
        return;
      }

      // Add user message and send
      addUserMessage(text);
      const currentMessages = [
        ...getApiMessages(),
        { role: "user", content: text },
      ];
      await sendMessage(currentMessages);
    },
    [exit, clearMessages, addUserMessage, getApiMessages, sendMessage, config, runDualAgent, addKnowledge, searchKnowledge, listKnowledge, clearKnowledge],
  );

  return (
    <Box flexDirection="column" paddingX={1}>
      {/* Welcome banner (show only when no messages) */}
      {messages.length === 0 && !isStreaming && (
        <>
          <WelcomeBanner content={welcomeMessage} theme={theme.colors} />
          <Text dimColor>
            Provider: {config.provider} | Model: {config.model}
          </Text>
          <Text>{" "}</Text>
        </>
      )}

      {/* Message history */}
      <ChatView
        messages={messages}
        theme={theme.colors}
        maxWidth={config.ui.panel_width ?? undefined}
      />

      {/* Streaming response in progress */}
      {isStreaming && streamingContent && (
        <Box
          flexDirection="column"
          borderStyle="round"
          borderColor={theme.colors.assistant_panel_border}
          paddingX={1}
          marginBottom={1}
        >
          <Box marginBottom={0}>
            <Text bold color={theme.colors.assistant_panel_border}>
              Assistant
            </Text>
          </Box>
          <MarkdownBlock content={streamingContent} theme={theme.colors} />
        </Box>
      )}

      {/* Dual agent mode */}
      {(dualAgentState.isRunning || dualAgentState.phases.length > 0) && (
        <DualAgentPanel state={dualAgentState} theme={theme.colors} />
      )}

      {/* Thinking spinner (before first token) */}
      {isStreaming && !streamingContent && (
        <ThinkingSpinner color={theme.colors.spinner} />
      )}

      {/* Timing info from last response */}
      {!isStreaming &&
        lastTimingRef.current !== null &&
        config.ui.show_timing && (
          <Text dimColor>{lastTimingRef.current}ms</Text>
        )}

      {/* Error display */}
      {error && (
        <Text color={theme.colors.error_text}>Error: {error}</Text>
      )}

      {/* Knowledge status */}
      {knowledgeState.isLoading && <Text dimColor>Loading knowledge...</Text>}
      {knowledgeState.lastResult && !knowledgeState.isLoading && (
        <Text dimColor>{knowledgeState.lastResult}</Text>
      )}
      {knowledgeState.error && (
        <Text color={theme.colors.error_text}>
          Knowledge error: {knowledgeState.error}
        </Text>
      )}
      {knowledgeState.items.length > 0 && !knowledgeState.isLoading && (
        <Box flexDirection="column" marginBottom={1}>
          {knowledgeState.items.map((item) => (
            <Text key={item.piece_id} dimColor>
              {item.piece_id.slice(0, 8)} {item.content.slice(0, 80)}
            </Text>
          ))}
        </Box>
      )}

      {/* Input area (hidden while streaming or dual agent running) */}
      {!isStreaming && !dualAgentState.isRunning && (
        <InputArea
          onSubmit={handleSubmit}
          promptChar={theme.symbols.input_prompt}
          promptColor={theme.colors.input_prompt}
        />
      )}
    </Box>
  );
};
