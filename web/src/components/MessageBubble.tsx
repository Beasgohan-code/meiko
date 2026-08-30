import { useEffect, useRef } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { Prism as SyntaxHighlighter } from "react-syntax-highlighter";
import { oneDark } from "react-syntax-highlighter/dist/esm/styles/prism";
import { Wrench, CheckCircle2, Circle, Loader2, Link2, ArrowRightLeft, Gauge } from "lucide-react";
import { animateMessageIn, animateThinkingDots } from "../lib/animations";
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
  const rowRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (rowRef.current) animateMessageIn(rowRef.current);
  }, [message.id]);

  const isUser = message.role === "user";

  return (
    <div className={`msg-row ${isUser ? "user" : "assistant"}`} ref={rowRef}>
      <div className={`avatar ${isUser ? "user" : "assistant"}`}>{isUser ? "U" : "M"}</div>
      <div>
        {!isUser && <PlanChecklist plan={message.plan} />}
        {!isUser && <ToolTrace tools={message.tools} />}
        {!isUser && <ProviderNotices notices={message.providerNotices} />}
        <div className="bubble">
          {!isUser && message.streaming && !message.content && <ThinkingIndicator />}
          <ReactMarkdown
            remarkPlugins={[remarkGfm]}
            components={{
              code({ className, children, ...props }: any) {
                const match = /language-(\w+)/.exec(className || "");
                return match ? (
                  <SyntaxHighlighter style={oneDark as any} language={match[1]} PreTag="div" customStyle={{ borderRadius: 10, fontSize: 12.5 }}>
                    {String(children).replace(/\n$/, "")}
                  </SyntaxHighlighter>
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
          {message.error && <div className="error-text">⚠ {message.error}</div>}
        </div>
        {!isUser && <Citations citations={message.citations} />}
        {!isUser && !message.streaming && <RunTelemetry info={message.runInfo} />}
      </div>
    </div>
  );
}
