import { randomUUID } from "node:crypto";

export interface MessageMetadata {
  model?: string;
  tokens_input?: number;
  tokens_output?: number;
  duration_ms?: number;
}

export interface ChatMessage {
  id: string;
  role: "system" | "user" | "assistant";
  content: string;
  timestamp: string;
  metadata?: MessageMetadata;
}

export function createMessage(
  role: ChatMessage["role"],
  content: string,
  metadata?: MessageMetadata,
): ChatMessage {
  return {
    id: randomUUID(),
    role,
    content,
    timestamp: new Date().toISOString(),
    metadata,
  };
}

export function toApiMessage(
  msg: ChatMessage,
): { role: string; content: string } {
  return { role: msg.role, content: msg.content };
}
