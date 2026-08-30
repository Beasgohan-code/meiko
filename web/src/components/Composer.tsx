import { useRef, useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { ArrowUp, Paperclip, Square, X, FileText, Image as ImageIcon, FileCode2, FileArchive } from "lucide-react";
import { pulseElement, shakeElement } from "../lib/animations";
import { useI18n } from "../lib/i18n";

interface PendingFile {
  file: File;
  id: string;
}

interface ComposerProps {
  onSend: (text: string) => void;
  onAttach: (file: File) => void;
  isStreaming: boolean;
  onStop: () => void;
}

function iconFor(file: File) {
  if (file.type.startsWith("image/")) return <ImageIcon size={13} />;
  if (/\.(py|js|ts|tsx|jsx|json|css|html)$/i.test(file.name)) return <FileCode2 size={13} />;
  if (/\.(zip|tar|gz)$/i.test(file.name)) return <FileArchive size={13} />;
  return <FileText size={13} />;
}

export default function Composer({ onSend, onAttach, isStreaming, onStop }: ComposerProps) {
  const { t } = useI18n();
  const [text, setText] = useState("");
  const [pending, setPending] = useState<PendingFile[]>([]);
  const [dragOver, setDragOver] = useState(false);
  const btnRef = useRef<HTMLButtonElement>(null);
  const wrapRef = useRef<HTMLDivElement>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const dragCounter = useRef(0);

  const addFiles = (files: FileList | File[]) => {
    const list = Array.from(files);
    setPending((p) => [...p, ...list.map((f) => ({ file: f, id: `${f.name}-${f.size}-${Math.random()}` }))]);
  };

  const removePending = (id: string) => setPending((p) => p.filter((f) => f.id !== id));

  const handleSend = () => {
    const trimmed = text.trim();
    if (!trimmed && pending.length === 0) {
      if (wrapRef.current) shakeElement(wrapRef.current);
      return;
    }
    if (btnRef.current) pulseElement(btnRef.current);
    pending.forEach((p) => onAttach(p.file));
    if (trimmed) onSend(trimmed);
    setText("");
    setPending([]);
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  return (
    <div className="composer-wrap">
      <div
        className={`composer ${dragOver ? "drag-over" : ""}`}
        ref={wrapRef}
        onDragEnter={(e) => {
          e.preventDefault();
          dragCounter.current++;
          setDragOver(true);
        }}
        onDragOver={(e) => e.preventDefault()}
        onDragLeave={() => {
          dragCounter.current--;
          if (dragCounter.current <= 0) setDragOver(false);
        }}
        onDrop={(e) => {
          e.preventDefault();
          dragCounter.current = 0;
          setDragOver(false);
          if (e.dataTransfer.files?.length) addFiles(e.dataTransfer.files);
        }}
      >
        <AnimatePresence>
          {dragOver && (
            <motion.div
              className="composer-drop-hint"
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
            >
              <Paperclip size={16} /> Drop files to attach
            </motion.div>
          )}
        </AnimatePresence>

        <div className="composer-col">
          <AnimatePresence>
            {pending.length > 0 && (
              <motion.div
                className="pending-files"
                initial={{ opacity: 0, height: 0 }}
                animate={{ opacity: 1, height: "auto" }}
                exit={{ opacity: 0, height: 0 }}
              >
                {pending.map((p) => (
                  <motion.div
                    key={p.id}
                    className="pending-file-chip"
                    layout
                    initial={{ opacity: 0, scale: 0.85 }}
                    animate={{ opacity: 1, scale: 1 }}
                    exit={{ opacity: 0, scale: 0.85 }}
                  >
                    {iconFor(p.file)}
                    <span className="pending-file-name">{p.file.name}</span>
                    <button onClick={() => removePending(p.id)} title="Remove">
                      <X size={11} />
                    </button>
                  </motion.div>
                ))}
              </motion.div>
            )}
          </AnimatePresence>

          <div className="composer-row">
            <button className="composer-btn" title={t("attach")} onClick={() => fileInputRef.current?.click()}>
              <Paperclip size={17} />
            </button>
            <input
              ref={fileInputRef}
              type="file"
              multiple
              accept="image/*,.pdf,.txt,.md,.csv,.json,.py,.zip"
              hidden
              onChange={(e) => {
                if (e.target.files?.length) addFiles(e.target.files);
                e.target.value = "";
              }}
            />
            <textarea
              placeholder={t("composerPlaceholder")}
              value={text}
              onChange={(e) => setText(e.target.value)}
              onKeyDown={handleKeyDown}
              onPaste={(e) => {
                if (e.clipboardData.files?.length) addFiles(e.clipboardData.files);
              }}
              rows={1}
              onInput={(e) => {
                const el = e.currentTarget;
                el.style.height = "auto";
                el.style.height = Math.min(el.scrollHeight, 160) + "px";
              }}
            />
            {isStreaming ? (
              <motion.button
                className="composer-btn"
                onClick={onStop}
                title="Stop"
                whileTap={{ scale: 0.9 }}
              >
                <Square size={15} />
              </motion.button>
            ) : (
              <motion.button
                ref={btnRef}
                className="composer-btn send-btn"
                onClick={handleSend}
                title="Send"
                whileHover={{ scale: 1.06 }}
                whileTap={{ scale: 0.9 }}
              >
                <ArrowUp size={17} />
              </motion.button>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
