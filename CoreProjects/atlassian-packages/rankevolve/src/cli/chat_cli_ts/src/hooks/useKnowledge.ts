// (c) Meta Platforms, Inc. and affiliates. Confidential and proprietary.

import { useCallback, useState } from "react";
import { execFileSync } from "node:child_process";

interface KnowledgeItem {
  piece_id: string;
  content: string;
}

interface KnowledgeState {
  isLoading: boolean;
  items: KnowledgeItem[];
  lastResult: string | null;
  error: string | null;
}

function runKnowledgeCli(
  command: string,
  text?: string,
): Record<string, unknown> {
  const args = [
    "run",
    "fbcode//rankevolve/src/knowledge:knowledge_cli",
    "--",
    command,
  ];
  if (text) {
    args.push(text);
  }

  const output = execFileSync("buck2", args, {
    encoding: "utf-8",
    timeout: 30000,
    env: { ...process.env },
  });

  // Find the last JSON line (skip buck build output)
  const lines = output.trim().split("\n");
  for (let i = lines.length - 1; i >= 0; i--) {
    try {
      return JSON.parse(lines[i]) as Record<string, unknown>;
    } catch {
      continue;
    }
  }
  throw new Error("No JSON output from knowledge CLI");
}

export function useKnowledge() {
  const [isLoading, setIsLoading] = useState(false);
  const [items, setItems] = useState<KnowledgeItem[]>([]);
  const [lastResult, setLastResult] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const addKnowledge = useCallback((text: string) => {
    setIsLoading(true);
    setError(null);
    try {
      const result = runKnowledgeCli("add", text);
      if (result.ok) {
        setLastResult(`Added (id: ${(result.piece_id as string).slice(0, 8)})`);
      } else {
        setError(result.error as string);
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setIsLoading(false);
    }
  }, []);

  const searchKnowledge = useCallback((query: string): string | null => {
    setIsLoading(true);
    setError(null);
    try {
      const result = runKnowledgeCli("search", query);
      if (result.ok) {
        const text = result.result as string;
        setLastResult(text);
        return text;
      }
      setError(result.error as string);
      return null;
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
      return null;
    } finally {
      setIsLoading(false);
    }
  }, []);

  const listKnowledge = useCallback(() => {
    setIsLoading(true);
    setError(null);
    try {
      const result = runKnowledgeCli("list");
      if (result.ok) {
        setItems(result.items as KnowledgeItem[]);
      } else {
        setError(result.error as string);
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setIsLoading(false);
    }
  }, []);

  const clearKnowledge = useCallback(() => {
    setIsLoading(true);
    setError(null);
    try {
      const result = runKnowledgeCli("clear");
      if (result.ok) {
        setItems([]);
        setLastResult(`Cleared ${result.cleared} items`);
      } else {
        setError(result.error as string);
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setIsLoading(false);
    }
  }, []);

  const state: KnowledgeState = {
    isLoading,
    items,
    lastResult,
    error,
  };

  return { state, addKnowledge, searchKnowledge, listKnowledge, clearKnowledge };
}
