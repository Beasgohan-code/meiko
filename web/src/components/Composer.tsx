import { useRef, useState } from "react";
import { ArrowUp, Paperclip, Square } from "lucide-react";
import { pulseElement, shakeElement } from "../lib/animations";

interface ComposerProps {
  onSend: (text: string) => void;
  onAttach: (file: File) => void;
  isStreaming: boolean;
  onStop: () => void;
}

export default function Composer({ onSend, onAttach, isStreaming, onStop }: ComposerProps) {
  const [text, setText] = useState("");
  const btnRef = useRef<HTMLButtonElement>(null);
  const wrapRef = useRef<HTMLDivElement>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const handleSend = () => {
    const trimmed = text.trim();
    if (!trimmed) {
      if (wrapRef.current) shakeElement(wrapRef.current);
      return;
    }
    if (btnRef.current) pulseElement(btnRef.current);
    onSend(trimmed);
    setText("");
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  return (
    <div className="composer-wrap">
      <div className="composer" ref={wrapRef}>
        <button className="composer-btn" title="Attach image or file" onClick={() => fileInputRef.current?.click()}>
          <Paperclip size={17} />
        </button>
        <input
          ref={fileInputRef}
          type="file"
          accept="image/*,.pdf,.txt,.md,.csv,.json,.py,.zip"
          hidden
          onChange={(e) => {
            const f = e.target.files?.[0];
            if (f) onAttach(f);
            e.target.value = "";
          }}
        />
        <textarea
          placeholder="Message Meiko… (Shift+Enter for newline)"
          value={text}
          onChange={(e) => setText(e.target.value)}
          onKeyDown={handleKeyDown}
          rows={1}
          onInput={(e) => {
            const el = e.currentTarget;
            el.style.height = "auto";
            el.style.height = Math.min(el.scrollHeight, 160) + "px";
          }}
        />
        {isStreaming ? (
          <button className="composer-btn" onClick={onStop} title="Stop">
            <Square size={15} />
          </button>
        ) : (
          <button ref={btnRef} className="composer-btn send-btn" onClick={handleSend} title="Send">
            <ArrowUp size={17} />
          </button>
        )}
      </div>
    </div>
  );
}
