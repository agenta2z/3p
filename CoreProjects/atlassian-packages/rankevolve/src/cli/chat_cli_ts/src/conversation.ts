import { ChatMessage, createMessage, toApiMessage } from "./schema.js";

export class Conversation {
  public messages: ChatMessage[] = [];

  constructor(public readonly systemPrompt: string) {}

  addUserMessage(content: string): ChatMessage {
    const msg = createMessage("user", content);
    this.messages.push(msg);
    return msg;
  }

  addAssistantMessage(
    content: string,
    metadata?: ChatMessage["metadata"],
  ): ChatMessage {
    const msg = createMessage("assistant", content, metadata);
    this.messages.push(msg);
    return msg;
  }

  getApiMessages(): Array<{ role: string; content: string }> {
    return this.messages.map(toApiMessage);
  }

  clear(): void {
    this.messages = [];
  }
}
