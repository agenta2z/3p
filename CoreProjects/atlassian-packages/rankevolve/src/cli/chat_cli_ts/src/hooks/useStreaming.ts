import { useCallback } from "react";

import type { LLMClient } from "../llm/base.js";
import type { AppConfig } from "../config.js";

interface StreamingCallbacks {
  onToken: (token: string) => void;
  onStart: () => void;
  onComplete: (fullText: string, startTime: number) => void;
  onError: (error: Error) => void;
}

export function useStreaming(
  client: LLMClient,
  config: AppConfig,
  systemPrompt: string,
  callbacks: StreamingCallbacks,
) {
  const sendMessage = useCallback(
    async (apiMessages: Array<{ role: string; content: string }>) => {
      callbacks.onStart();
      let fullText = "";
      const startTime = Date.now();

      try {
        const stream = client.streamResponse({
          messages: apiMessages,
          system: systemPrompt,
          model: config.model,
          maxTokens: config.max_tokens,
          temperature: config.temperature,
        });

        for await (const token of stream) {
          fullText += token;
          callbacks.onToken(token);
        }

        callbacks.onComplete(fullText, startTime);
      } catch (err) {
        callbacks.onError(
          err instanceof Error ? err : new Error(String(err)),
        );
      }
    },
    [client, config, systemPrompt, callbacks],
  );

  return { sendMessage };
}
