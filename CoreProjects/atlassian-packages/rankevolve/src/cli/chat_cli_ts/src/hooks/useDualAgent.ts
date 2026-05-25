import { useCallback, useRef, useState } from "react";
import { spawn, type ChildProcess } from "node:child_process";
import { createInterface } from "node:readline";

export interface DualAgentTokenEvent {
  chunk: string;
  phase: string;
  agent_id: string;
}

export interface DualAgentState {
  isRunning: boolean;
  phases: CompletedPhase[];
  currentPhase: string | null;
  currentAgent: string | null;
  streamingContent: string;
  error: string | null;
}

interface CompletedPhase {
  phase: string;
  agent_id: string;
  content: string;
}

interface UseDualAgentOptions {
  rootFolder: string;
}

export function useDualAgent({ rootFolder }: UseDualAgentOptions) {
  const [isRunning, setIsRunning] = useState(false);
  const [phases, setPhases] = useState<CompletedPhase[]>([]);
  const [currentPhase, setCurrentPhase] = useState<string | null>(null);
  const [currentAgent, setCurrentAgent] = useState<string | null>(null);
  const [streamingContent, setStreamingContent] = useState("");
  const [error, setError] = useState<string | null>(null);

  const processRef = useRef<ChildProcess | null>(null);
  const phaseContentRef = useRef<string>("");
  const currentPhaseRef = useRef<string | null>(null);
  const currentAgentRef = useRef<string | null>(null);

  const finalizeCurrentPhase = useCallback(() => {
    if (currentPhaseRef.current && phaseContentRef.current) {
      const completed: CompletedPhase = {
        phase: currentPhaseRef.current,
        agent_id: currentAgentRef.current ?? "",
        content: phaseContentRef.current,
      };
      setPhases((prev) => [...prev, completed]);
    }
    phaseContentRef.current = "";
    setStreamingContent("");
  }, []);

  const runDualAgent = useCallback(
    (request: string) => {
      setIsRunning(true);
      setPhases([]);
      setCurrentPhase(null);
      setCurrentAgent(null);
      setStreamingContent("");
      setError(null);
      phaseContentRef.current = "";
      currentPhaseRef.current = null;
      currentAgentRef.current = null;

      const child = spawn(
        "buck",
        [
          "run",
          "fbcode//rankevolve/src/cli/chat_cli:dual_inferencer_cli",
          "--",
          "-r",
          rootFolder,
          "-q",
          request,
        ],
        {
          stdio: ["ignore", "pipe", "pipe"],
          env: { ...process.env },
        },
      );

      processRef.current = child;

      let stderrBuffer = "";

      if (child.stderr) {
        child.stderr.on("data", (data: Buffer) => {
          stderrBuffer += data.toString();
        });
      }

      if (child.stdout) {
        const rl = createInterface({ input: child.stdout });

        rl.on("line", (line: string) => {
          const trimmed = line.trim();
          if (!trimmed) return;

          let event: Record<string, unknown>;
          try {
            event = JSON.parse(trimmed) as Record<string, unknown>;
          } catch {
            return; // Skip non-JSON lines (e.g., buck build output)
          }

          if (event.event === "token") {
            const chunk = (event.chunk as string) ?? "";
            const phase = (event.phase as string) ?? "";
            const agentId = (event.agent_id as string) ?? "";

            // Phase transition detection
            if (
              phase !== currentPhaseRef.current ||
              agentId !== currentAgentRef.current
            ) {
              finalizeCurrentPhase();
              currentPhaseRef.current = phase;
              currentAgentRef.current = agentId;
              setCurrentPhase(phase);
              setCurrentAgent(agentId);
            }

            phaseContentRef.current += chunk;
            setStreamingContent((prev) => prev + chunk);
          } else if (event.event === "complete") {
            finalizeCurrentPhase();
            currentPhaseRef.current = null;
            currentAgentRef.current = null;
            setCurrentPhase(null);
            setCurrentAgent(null);
            setIsRunning(false);
          } else if (event.event === "error") {
            setError((event.message as string) ?? "Unknown error");
            setIsRunning(false);
          }
        });
      }

      child.on("close", (code: number | null) => {
        processRef.current = null;
        if (code !== null && code !== 0) {
          // Non-zero exit without a "complete" event means crash
          const errMsg =
            stderrBuffer.trim().split("\n").pop() ??
            `Process exited with code ${code}`;
          setError((prev) => prev ?? errMsg);
          setIsRunning(false);
        }
      });

      child.on("error", (err: Error) => {
        processRef.current = null;
        setError(err.message);
        setIsRunning(false);
      });
    },
    [rootFolder, finalizeCurrentPhase],
  );

  const abort = useCallback(() => {
    if (processRef.current) {
      processRef.current.kill("SIGTERM");
      processRef.current = null;
      setIsRunning(false);
      setError("Aborted by user");
    }
  }, []);

  const state: DualAgentState = {
    isRunning,
    phases,
    currentPhase,
    currentAgent,
    streamingContent,
    error,
  };

  return { state, runDualAgent, abort };
}
