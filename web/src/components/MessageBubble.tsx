import { useEffect, useRef, useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { Prism as SyntaxHighlighter } from "react-syntax-highlighter";
import { oneDark } from "react-syntax-highlighter/dist/esm/styles/prism";
import { Wrench, CheckCircle2, Circle, Loader2, Link2, ArrowRightLeft, Gauge, Brain, ChevronDown, Copy, Check, Zap } from "lucide-react";
import { animateThinkingDots } from "../lib/animations";
import type { ChatMessage } from "../lib/store";

interface Props {
  message: ChatMessage;
}

function PlanChecklist({ plan }: { plan: ChatMessage["plan"] }) {
  if (!plan || !plan.length) return null;
  const done = plan.filter((t) => t.status === "done").length;
  return (
    <div className="plan-checklist">
      <div className="plan-checklist-header">Plan · {done}/{plan.length} done</div>
      {plan.map((t, i) => (
        <div key={i} className={`plan-task plan-task-${t.status}`}>
          {t.status === "done" ? (
            <CheckCircle2 size={14} color="#4ade80" />
          ) : t.status === "in_progress" ? (
            <Loader2 size={14} className="spin-icon" />
          ) : (
            <Circle size={14} color="#6b7280" />
          )}
          <span>{t.text}</span>
        </div>
      ))}
    </div>
  );
}

function CopyCodeButton({ text }: { text: string }) {
  const [copied, setCopied] = useState(false);
  return (
    <motion.button
      className="code-copy-btn"
      title="Copy code"
      whileTap={{ scale: 0.9 }}
      onClick={async () => {
        try {
          await navigator.clipboard.writeText(text);
        } catch {
          /* clipboard unavailable — ignore */
        }
        setCopied(true);
        setTimeout(() => setCopied(false), 1500);
      }}
    >
      <AnimatePresence mode="wait" initial={false}>
        <motion.span
          key={copied ? "copied" : "copy"}
          initial={{ opacity: 0, y: -4 }}
          animate={{ opacity: 1, y: 0 }}
          exit={{ opacity: 0, y: 4 }}
          transition={{ duration: 0.12 }}
          style={{ display: "inline-flex", alignItems: "center", gap: 5 }}
        >
          {copied ? <Check size={13} /> : <Copy size={13} />}
          {copied ? "Copied" : "Copy"}
        </motion.span>
      </AnimatePresence>
    </motion.button>
  );
}

/**
 * Collapsible "Thinking" trace — DeepSeek-R1/QwQ/Gemini-Thinking-style chain
 * of thought, and Claude's "Extended Thinking" UI, rendered separately from
 * the final answer so users can inspect the model's reasoning without it
 * cluttering the response.
 */
function ThinkingPanel({ text, isThinking }: { text?: string; isThinking?: boolean }) {
  const [open, setOpen] = useState(false);
  useEffect(() => {
    if (isThinking) setOpen(true);
  }, [isThinking]);
  if (!text) return null;
  return (
    <motion.div
      className={`thinking-panel ${isThinking ? "active" : ""}`}
      layout
      initial={{ opacity: 0, y: -6 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.25 }}
    >
      <button className="thinking-panel-header" onClick={() => setOpen((o) => !o)}>
        <Brain size={13} className={isThinking ? "spin-icon" : ""} />
        <span>{isThinking ? "Thinking…" : "Thought process"}</span>
        <ChevronDown size={13} className={`chevron ${open ? "open" : ""}`} />
      </button>
      <AnimatePresence initial={false}>
        {open && (
          <motion.div
            className="thinking-panel-body"
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: "auto", opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            transition={{ duration: 0.2, ease: "easeInOut" }}
            style={{ overflow: "hidden" }}
          >
            <div style={{ paddingTop: 0 }}>{text}</div>
          </motion.div>
        )}
      </AnimatePresence>
    </motion.div>
  );
}

function ProviderNotices({ notices }: { notices?: string[] }) {
  if (!notices || !notices.length) return null;
  return (
    <div className="provider-notices">
      {notices.map((n, i) => (
        <div key={i} className="provider-notice">
          <ArrowRightLeft size={12} /> {n}
        </div>
      ))}
    </div>
  );
}

function Citations({ citations }: { citations?: ChatMessage["citations"] }) {
  if (!citations || !citations.length) return null;
  return (
    <div className="citations">
      <div className="citations-header">
        <Link2 size={12} /> Sources
      </div>
      <div className="citations-list">
        {citations.map((c, i) => (
          <a key={i} href={c.url} target="_blank" rel="noopener noreferrer" className="citation-chip" title={c.url}>
            {(() => {
              try {
                return new URL(c.url).hostname.replace(/^www\./, "");
              } catch {
                return c.url;
              }
            })()}
          </a>
        ))}
      </div>
    </div>
  );
}

function ToolTrace({ tools }: { tools: ChatMessage["tools"] }) {
  if (!tools.length) return null;
  return (
    <div className="tool-trace">
      {tools.map((t) => (
        <div key={t.id} className={`tool-badge ${t.status}`}>
          <span className="tool-icon">
            {t.status === "calling" ? <span className="spinner" /> : <CheckCircle2 size={13} color="#4ade80" />}
          </span>
          <Wrench size={12} />
          <span className="tool-name">{t.name}</span>
          {t.result && <span className="tool-result">{t.result.slice(0, 90)}</span>}
        </div>
      ))}
    </div>
  );
}

function RunTelemetry({ info }: { info?: ChatMessage["runInfo"] }) {
  if (!info || !info.provider) return null;
  const parts: string[] = [info.model ? `${info.provider} · ${info.model}` : info.provider];
  if (typeof info.elapsedSeconds === "number") parts.push(`${info.elapsedSeconds.toFixed(1)}s`);
  if (info.steps) parts.push(`${info.steps} step${info.steps === 1 ? "" : "s"}`);
  if (info.toolCalls) parts.push(`${info.toolCalls} tool call${info.toolCalls === 1 ? "" : "s"}`);
  if (info.providerSwitches) parts.push(`${info.providerSwitches} fallback${info.providerSwitches === 1 ? "" : "s"}`);
  return (
    <div className="run-telemetry" title="Which provider/model actually answered, and how long it took">
      <Gauge size={11} />
      {parts.join(" · ")}
      {typeof info.tokensPerSecond === "number" && info.tokensPerSecond > 0 && (
        <span className="tokens-per-sec" title="Estimated generation speed (Groq-style)">
          <Zap size={11} /> {info.tokensPerSecond} tok/s
        </span>
      )}
    </div>
  );
}

function ThinkingIndicator() {
  const ref = useRef<HTMLDivElement>(null);
  useEffect(() => {
    if (ref.current) animateThinkingDots(ref.current);
  }, []);
  return (
    <div className="thinking-dots" ref={ref}>
      <span className="dot" />
      <span className="dot" />
      <span className="dot" />
    </div>
  );
}

export default function MessageBubble({ message }: Props) {
  const isUser = message.role === "user";

  return (
    <motion.div
      className={`msg-row ${isUser ? "user" : "assistant"}`}
      layout="position"
      initial={{ opacity: 0, y: 16, scale: 0.98 }}
      animate={{ opacity: 1, y: 0, scale: 1 }}
      transition={{ duration: 0.42, ease: [0.16, 1, 0.3, 1] }}
    >
      <div className={`avatar ${isUser ? "user" : "assistant"}`}>{isUser ? "U" : "M"}</div>
      <div style={{ minWidth: 0 }}>
        {!isUser && <ThinkingPanel text={message.thinking} isThinking={message.isThinking} />}
        {!isUser && <PlanChecklist plan={message.plan} />}
        {!isUser && <ToolTrace tools={message.tools} />}
        {!isUser && <ProviderNotices notices={message.providerNotices} />}
        <div className="bubble">
          {!isUser && message.streaming && !message.content && !message.thinking && <ThinkingIndicator />}
          <ReactMarkdown
            remarkPlugins={[remarkGfm]}
            components={{
              code({ className, children, ...props }: any) {
                const match = /language-(\w+)/.exec(className || "");
                const codeText = String(children).replace(/\n$/, "");
                return match ? (
                  <div className="code-block-wrap">
                    <div className="code-block-header">
                      <span className="code-block-lang">{match[1]}</span>
                      <CopyCodeButton text={codeText} />
                    </div>
                    <SyntaxHighlighter style={oneDark as any} language={match[1]} PreTag="div" customStyle={{ borderRadius: "0 0 10px 10px", fontSize: 12.5, margin: 0 }}>
                      {codeText}
                    </SyntaxHighlighter>
                  </div>
                ) : (
                  <code className={className} {...props}>
                    {children}
                  </code>
                );
              },
            }}
          >
            {message.content}
          </ReactMarkdown>
          {!isUser && message.streaming && message.content && !message.isThinking && (
            <span className="stream-caret" aria-hidden="true" />
          )}
          {message.error && <div className="error-text">⚠ {message.error}</div>}
        </div>
        {!isUser && <Citations citations={message.citations} />}
        {!isUser && !message.streaming && <RunTelemetry info={message.runInfo} />}
      </div>
    </motion.div>
  );
}
