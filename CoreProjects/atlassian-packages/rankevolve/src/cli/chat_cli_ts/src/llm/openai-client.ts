import OpenAI from "openai";

import type { LLMClient, StreamParams } from "./base.js";

export class OpenAIClient implements LLMClient {
  private client: OpenAI;

  constructor(apiKey: string, baseUrl?: string) {
    this.client = new OpenAI({
      apiKey,
      ...(baseUrl ? { baseURL: baseUrl } : {}),
    });
  }

  async *streamResponse(params: StreamParams): AsyncIterable<string> {
    const messages: OpenAI.ChatCompletionMessageParam[] = [
      { role: "system" as const, content: params.system },
      ...(params.messages as OpenAI.ChatCompletionMessageParam[]),
    ];

    const stream = await this.client.chat.completions.create({
      model: params.model,
      messages,
      max_tokens: params.maxTokens,
      temperature: params.temperature,
      stream: true,
    });

    for await (const chunk of stream) {
      const text = chunk.choices[0]?.delta?.content;
      if (text) {
        yield text;
      }
    }
  }

  async close(): Promise<void> {
    // OpenAI TS SDK doesn't require explicit close
  }
}
