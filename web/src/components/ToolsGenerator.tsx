import { useEffect, useState } from "react";
import { motion } from "framer-motion";
import { Wrench, X, Trash2, Plus, Globe, Code2 } from "lucide-react";
import { GeneratedTool, deleteGeneratedTool, fetchGeneratedTools, generateTool } from "../lib/api";

interface Props {
  onClose: () => void;
}

/**
 * Dev-mode "tools generator": describe a tool in a short form and Meiko
 * registers a *real* backend Tool the agent can call in future
 * conversations — either an HTTP call to any URL template, or a small
 * Python snippet — without hand-writing/deploying a new Tool subclass.
 */
export default function ToolsGenerator({ onClose }: Props) {
  const [tools, setTools] = useState<GeneratedTool[]>([]);
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [kind, setKind] = useState<"http" | "python">("http");
  const [httpMethod, setHttpMethod] = useState("GET");
  const [httpUrlTemplate, setHttpUrlTemplate] = useState("https://api.example.com/{query}");
  const [pythonBody, setPythonBody] = useState("result = 'hello from your generated tool'");
  const [status, setStatus] = useState("");
  const [error, setError] = useState("");

  const refresh = () => fetchGeneratedTools().then(setTools).catch(() => {});
  useEffect(() => {
    refresh();
  }, []);

  const handleGenerate = async () => {
    setError("");
    setStatus("Generating…");
    try {
      await generateTool({
        name: name.trim(),
        description: description.trim(),
        kind,
        http_method: kind === "http" ? httpMethod : undefined,
        http_url_template: kind === "http" ? httpUrlTemplate.trim() : undefined,
        python_body: kind === "python" ? pythonBody : undefined,
      });
      setStatus("Tool created ✓ — Meiko can use it starting next message.");
      setName("");
      setDescription("");
      refresh();
      setTimeout(() => setStatus(""), 3000);
    } catch (e: any) {
      setError(e?.message || "Failed to generate tool");
      setStatus("");
    }
  };

  const handleDelete = async (toolName: string) => {
    await deleteGeneratedTool(toolName);
    refresh();
  };

  return (
    <motion.div
      className="tools-gen-panel glass-strong"
      initial={{ opacity: 0, y: 16, scale: 0.97 }}
      animate={{ opacity: 1, y: 0, scale: 1 }}
      exit={{ opacity: 0, y: 12, scale: 0.97 }}
      transition={{ duration: 0.2, ease: [0.16, 1, 0.3, 1] }}
    >
      <div className="dev-console-header">
        <span style={{ display: "flex", alignItems: "center", gap: 8 }}>
          <Wrench size={16} /> Tools Generator
        </span>
        <button className="icon-btn" title="Close" onClick={onClose}>
          <X size={16} />
        </button>
      </div>

      <div className="tools-gen-body">
        <p className="field-hint" style={{ marginBottom: 8 }}>
          Describe a tool once — Meiko registers it as a real callable tool for every future
          conversation. HTTP tools call any URL template you give; Python tools run a short snippet
          in a sandboxed subprocess.
        </p>

        <input
          type="text"
          placeholder="Tool name (snake_case, e.g. get_stock_price)"
          value={name}
          onChange={(e) => setName(e.target.value)}
        />
        <textarea
          placeholder="What does this tool do? (shown to the agent so it knows when to use it)"
          value={description}
          onChange={(e) => setDescription(e.target.value)}
          rows={2}
          style={{ marginTop: 8 }}
        />

        <div className="dev-console-kind-toggle" style={{ marginTop: 8 }}>
          <button className={kind === "http" ? "active" : ""} onClick={() => setKind("http")}>
            <Globe size={12} style={{ marginRight: 5 }} /> HTTP
          </button>
          <button className={kind === "python" ? "active" : ""} onClick={() => setKind("python")}>
            <Code2 size={12} style={{ marginRight: 5 }} /> Python
          </button>
        </div>

        {kind === "http" ? (
          <>
            <select
              value={httpMethod}
              onChange={(e) => setHttpMethod(e.target.value)}
              className="lang-select"
              style={{ marginTop: 8 }}
            >
              {["GET", "POST", "PUT", "DELETE"].map((m) => (
                <option key={m} value={m}>
                  {m}
                </option>
              ))}
            </select>
            <input
              type="text"
              placeholder="URL template, e.g. https://api.example.com/weather?city={city}"
              value={httpUrlTemplate}
              onChange={(e) => setHttpUrlTemplate(e.target.value)}
              style={{ marginTop: 8 }}
            />
            <div className="field-hint">Use {"{placeholder}"} for arguments the agent will fill in.</div>
          </>
        ) : (
          <>
            <textarea
              className="dev-console-editor"
              value={pythonBody}
              onChange={(e) => setPythonBody(e.target.value)}
              rows={6}
              spellCheck={false}
              style={{ marginTop: 8 }}
            />
            <div className="field-hint">
              Runs in its own sandboxed subprocess (never in-process). Set a <code>result</code> string
              variable with the tool's output.
            </div>
          </>
        )}

        {error && <div className="field-hint" style={{ color: "var(--danger, #ff6b6b)" }}>{error}</div>}

        <motion.button
          className="new-chat-btn"
          style={{ justifyContent: "center", marginTop: 10, width: "100%" }}
          onClick={handleGenerate}
          disabled={!name.trim() || !description.trim()}
          whileHover={{ scale: 1.02 }}
          whileTap={{ scale: 0.97 }}
        >
          <Plus size={14} style={{ marginRight: 6 }} /> {status || "Generate tool"}
        </motion.button>

        {tools.length > 0 && (
          <div className="dev-console-history" style={{ marginTop: 14 }}>
            <div className="dev-console-label">Generated tools ({tools.length})</div>
            {tools.map((tool) => (
              <div key={tool.name} className="tools-gen-row">
                <div className="tools-gen-row-meta">
                  <span className="artifact-name">{tool.name}</span>
                  <span className="artifact-sub">{tool.kind} · {tool.description.slice(0, 60)}</span>
                </div>
                <button className="icon-btn" title="Delete" onClick={() => handleDelete(tool.name)}>
                  <Trash2 size={13} />
                </button>
              </div>
            ))}
          </div>
        )}
      </div>
    </motion.div>
  );
}
