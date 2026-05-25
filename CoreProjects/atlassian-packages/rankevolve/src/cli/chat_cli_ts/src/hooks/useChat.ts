import { useCallback, useState } from "react";

import type { MessageMetadata, ChatMessage } from "../schema.js";
import { createMessage, toApiMessage } from "../schema.js";

export function useChat(systemPrompt: string) {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [isStreaming, setIsStreaming] = useState(false);
  const [streamingContent, setStreamingContent] = useState("");
  const [error, setError] = useState<string | null>(null);

  const addUserMessage = useCallback((content: string): ChatMessage => {
    const msg = createMessage("user", content);
    setMessages((prev) => [...prev, msg]);
    return msg;
  }, []);

  const addAssistantMessage = useCallback(
    (content: string, metadata?: MessageMetadata): ChatMessage => {
      const msg = createMessage("assistant", content, metadata);
      setMessages((prev) => [...prev, msg]);
      setStreamingContent("");
      return msg;
    },
    [],
  );

  const appendStreamingToken = useCallback((token: string) => {
    setStreamingContent((prev) => prev + token);
  }, []);

  const getApiMessages = useCallback((): Array<{
    role: string;
    content: string;
  }> => {
    return messages.map(toApiMessage);
  }, [messages]);

  const clearMessages = useCallback(() => {
    setMessages([]);
    setStreamingContent("");
    setError(null);
  }, []);

  return {
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
  };
}
