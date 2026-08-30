import { useEffect, useRef, useState } from "react";
import { motion } from "framer-motion";
import { Terminal, Play, Square, X, Trash2, Code2 } from "lucide-react";
import { ConsoleRun, connectConsoleSocket, fetchConsoleRuns, startConsoleRun, stopConsoleRun } from "../lib/api";

interface Props {
  sessionId: string;
  onClose: () => void;
}

const SNIPPETS: Record<"bash" | "python", string> = {
  bash: "echo 'Hello from Meiko Dev Console' && ls -la",
  python: "print('Hello from Meiko Dev Console')\nfor i in range(3):\n    print(i)",
};

/**
 * Arena.ai / menus.ai-style dev console: a command editor + "Run" button
 * that streams real, live output as the process runs (not a spinner that
 * resolves once at the end), plus per-run history and a stop button — the
 * same shape as this project's own `get_process_output` sandbox tool,
 * surfaced as a real UI instead of only being usable by the agent.
 */
export default function DevConsole({ sessionId, onClose }: Props) {
  const [kind, setKind] = useState<"bash" | "python">("bash");
  const [command, setCommand] = useState(SNIPPETS.bash);
  const [output, setOutput] = useState("");
  const [activeRun, setActiveRun] = useState<ConsoleRun | null>(null);
  const [history, setHistory] = useState<ConsoleRun[]>([]);
  const [error, setError] = useState("");
  const outputRef = useRef<HTMLPreElement>(null);
  const socketRef = useRef<{ close: () => void } | null>(null);

  const refreshHistory = () => fetchConsoleRuns(sessionId).then(setHistory).catch(() => {});

  useEffect(() => {
    refreshHistory();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [sessionId]);

  useEffect(() => {
    outputRef.current?.scrollTo({ top: outputRef.current.scrollHeight });
  }, [output]);

  useEffect(() => () => socketRef.current?.close(), []);

  const handleRun = async () => {
    setError("");
    setOutput("");
    socketRef.current?.close();
    try {
      const run = await startConsoleRun(sessionId, command, kind, 60);
      setActiveRun(run);
      const socket = connectConsoleSocket(run.run_id, (msg) => {
        if (msg.event === "output" && msg.text) {
          setOutput((prev) => prev + msg.text);
        } else if (msg.event === "exit") {
          setActiveRun((prev) => (prev ? { ...prev, status: (msg.status as any) || "exited", exit_code: msg.exit_code ?? null } : prev));
          refreshHistory();
        }
      });
      socketRef.current = socket;
    } catch (e: any) {
      setError(e?.message || "Failed to start run");
    }
  };

  const handleStop = async () => {
    if (activeRun) await stopConsoleRun(activeRun.run_id);
  };

  const isRunning = activeRun?.status === "running";

  return (
    <motion.div
      className="dev-console glass-strong"
      initial={{ opacity: 0, y: 16, scale: 0.97 }}
      animate={{ opacity: 1, y: 0, scale: 1 }}
      exit={{ opacity: 0, y: 12, scale: 0.97 }}
      transition={{ duration: 0.2, ease: [0.16, 1, 0.3, 1] }}
    >
      <div className="dev-console-header">
        <span style={{ display: "flex", alignItems: "center", gap: 8 }}>
          <Terminal size={16} /> Dev Console
        </span>
        <div style={{ display: "flex", gap: 6, alignItems: "center" }}>
          <div className="dev-console-kind-toggle">
            <button
              className={kind === "bash" ? "active" : ""}
              onClick={() => {
                setKind("bash");
                if (command === SNIPPETS.python) setCommand(SNIPPETS.bash);
              }}
            >
              bash
            </button>
            <button
              className={kind === "python" ? "active" : ""}
              onClick={() => {
                setKind("python");
                if (command === SNIPPETS.bash) setCommand(SNIPPETS.python);
              }}
            >
              python
            </button>
          </div>
          <button className="icon-btn" title="Close" onClick={onClose}>
            <X size={16} />
          </button>
        </div>
      </div>

      <div className="dev-console-body">
        <div className="dev-console-editor-col">
          <div className="dev-console-label">
            <Code2 size={12} /> Command / script
          </div>
          <textarea
            className="dev-console-editor"
            value={command}
            onChange={(e) => setCommand(e.target.value)}
            spellCheck={false}
            rows={8}
          />
          <div style={{ display: "flex", gap: 8, marginTop: 8 }}>
            <motion.button
              className="new-chat-btn"
              style={{ flex: 1, justifyContent: "center" }}
              onClick={handleRun}
              disabled={isRunning}
              whileHover={{ scale: isRunning ? 1 : 1.02 }}
              whileTap={{ scale: isRunning ? 1 : 0.97 }}
            >
              <Play size={14} style={{ marginRight: 6 }} /> {isRunning ? "Running…" : "Run"}
            </motion.button>
            {isRunning && (
              <button className="icon-btn" title="Stop" onClick={handleStop} style={{ padding: "0 12px" }}>
                <Square size={14} />
              </button>
            )}
          </div>
          {error && <div className="field-hint" style={{ color: "var(--danger, #ff6b6b)", marginTop: 6 }}>{error}</div>}

          {history.length > 0 && (
            <div className="dev-console-history">
              <div className="dev-console-label" style={{ marginTop: 12 }}>
                Recent runs
              </div>
              {history.slice(0, 8).map((r) => (
                <div key={r.run_id} className={`dev-console-history-row status-${r.status}`}>
                  <span className="cmd">{r.command.slice(0, 40)}</span>
                  <span className="status">{r.status}</span>
                </div>
              ))}
            </div>
          )}
        </div>

        <div className="dev-console-output-col">
          <div className="dev-console-label">
            Output {activeRun && <span className={`run-status-pill status-${activeRun.status}`}>{activeRun.status}</span>}
          </div>
          <pre className="dev-console-output" ref={outputRef}>
            {output || "Output will stream here as your command runs…"}
          </pre>
        </div>
      </div>
    </motion.div>
  );
}
