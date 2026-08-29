import { useEffect, useRef } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { Prism as SyntaxHighlighter } from "react-syntax-highlighter";
import { oneDark } from "react-syntax-highlighter/dist/esm/styles/prism";
import { Wrench, CheckCircle2 } from "lucide-react";
import { animateMessageIn, animateThinkingDots } from "../lib/animations";
import type { ChatMessage } from "../lib/store";

interface Props {
  message: ChatMessage;
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
        {!isUser && <ToolTrace tools={message.tools} />}
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
      </div>
    </div>
  );
}
