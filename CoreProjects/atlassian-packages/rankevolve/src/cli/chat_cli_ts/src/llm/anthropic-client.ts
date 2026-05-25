import Anthropic from "@anthropic-ai/sdk";

import type { LLMClient, StreamParams } from "./base.js";

export class AnthropicClient implements LLMClient {
  private client: Anthropic;

  constructor(apiKey: string, baseUrl?: string) {
    this.client = new Anthropic({
      apiKey,
      ...(baseUrl ? { baseURL: baseUrl } : {}),
    });
  }

  async *streamResponse(params: StreamParams): AsyncIterable<string> {
    const stream = this.client.messages.stream({
      model: params.model,
      max_tokens: params.maxTokens,
      temperature: params.temperature,
      system: params.system,
      messages: params.messages as Anthropic.MessageParam[],
    });

    for await (const event of stream) {
      if (
        event.type === "content_block_delta" &&
        event.delta.type === "text_delta"
      ) {
        yield event.delta.text;
      }
    }
  }

  async close(): Promise<void> {
    // Anthropic TS SDK doesn't require explicit close
  }
}
