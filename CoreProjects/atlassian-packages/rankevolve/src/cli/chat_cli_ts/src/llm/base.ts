export interface StreamParams {
  messages: Array<{ role: string; content: string }>;
  system: string;
  model: string;
  maxTokens: number;
  temperature: number;
}

export interface LLMClient {
  streamResponse(params: StreamParams): AsyncIterable<string>;
  close(): Promise<void>;
}
