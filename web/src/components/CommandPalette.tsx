import { useEffect, useMemo, useRef, useState } from "react";
import { AnimatePresence, motion } from "framer-motion";
import {
  Sparkles,
  MessageSquarePlus,
  Settings,
  Sun,
  Moon,
  FolderOpen,
  Code2,
  Search as SearchIcon,
  GraduationCap,
  Rocket,
  Cpu,
  Image as ImageIcon,
  CornerDownLeft,
} from "lucide-react";
import type { AgentModeMeta } from "../lib/api";

/**
 * menus.ai / Arena / Raycast-style global command palette — press
 * Cmd/Ctrl+K anywhere in the app to open a full-screen liquid-glass
 * search-and-act menu: jump modes, open settings, toggle theme, start a
 * vibe-coding or study session, or just run a prompt directly.
 */
export interface CommandItem {
  id: string;
  label: string;
  hint?: string;
  icon: React.ReactNode;
  keywords?: string;
  action: () => void;
  group: string;
}

interface Props {
  open: boolean;
  onClose: () => void;
  modes: AgentModeMeta[];
  theme: "dark" | "light";
  onNewChat: () => void;
  onOpenSettings: () => void;
  onOpenArtifacts: () => void;
  onToggleTheme: () => void;
  onSetMode: (id: string) => void;
  onRunPrompt: (text: string) => void;
}

const MODE_ICON: Record<string, React.ReactNode> = {
  "message-circle": <Sparkles size={16} />,
  search: <SearchIcon size={16} />,
  code: <Code2 size={16} />,
  cpu: <Cpu size={16} />,
  image: <ImageIcon size={16} />,
};

export default function CommandPalette({
  open,
  onClose,
  modes,
  theme,
  onNewChat,
  onOpenSettings,
  onOpenArtifacts,
  onToggleTheme,
  onSetMode,
  onRunPrompt,
}: Props) {
  const [query, setQuery] = useState("");
  const [activeIndex, setActiveIndex] = useState(0);
  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    if (open) {
      setQuery("");
      setActiveIndex(0);
      requestAnimationFrame(() => inputRef.current?.focus());
    }
  }, [open]);

  const items: CommandItem[] = useMemo(() => {
    const base: CommandItem[] = [
      {
        id: "new-chat",
        label: "New chat",
        hint: "Start a fresh conversation",
        icon: <MessageSquarePlus size={16} />,
        action: onNewChat,
        group: "Actions",
      },
      {
        id: "settings",
        label: "Open settings",
        hint: "Providers, connectors, skills, memory",
        icon: <Settings size={16} />,
        action: onOpenSettings,
        group: "Actions",
      },
      {
        id: "artifacts",
        label: "Open artifacts",
        hint: "Files Meiko has generated",
        icon: <FolderOpen size={16} />,
        action: onOpenArtifacts,
        group: "Actions",
      },
      {
        id: "theme",
        label: theme === "dark" ? "Switch to light mode" : "Switch to dark mode",
        icon: theme === "dark" ? <Sun size={16} /> : <Moon size={16} />,
        action: onToggleTheme,
        group: "Actions",
      },
      {
        id: "vibe",
        label: "Start Vibe Coding",
        hint: "Prototype an app from a plain-language idea",
        icon: <Rocket size={16} />,
        keywords: "vibe code build prototype",
        action: () => onRunPrompt("/vibe "),
        group: "Quick start",
      },
      {
        id: "study",
        label: "Start a Study session",
        hint: "Flashcards + graded quiz on any topic",
        icon: <GraduationCap size={16} />,
        keywords: "study quiz flashcards tutor omnitutor",
        action: () => onRunPrompt("/study "),
        group: "Quick start",
      },
    ];
    const modeItems: CommandItem[] = modes.map((m) => ({
      id: `mode-${m.id}`,
      label: `Switch to ${m.name} mode`,
      hint: m.description,
      icon: MODE_ICON[m.icon] || <Sparkles size={16} />,
      keywords: `mode ${m.id}`,
      action: () => onSetMode(m.id),
      group: "Modes",
    }));
    const all = [...base, ...modeItems];
    if (query.trim()) {
      all.push({
        id: "run-query",
        label: `Ask Meiko: "${query.trim()}"`,
        hint: "Send this as a message",
        icon: <CornerDownLeft size={16} />,
        action: () => onRunPrompt(query.trim()),
        group: "Ask",
      });
    }
    const q = query.trim().toLowerCase();
    if (!q) return all;
    return all.filter(
      (it) =>
        it.label.toLowerCase().includes(q) ||
        it.hint?.toLowerCase().includes(q) ||
        it.keywords?.toLowerCase().includes(q) ||
        it.id === "run-query"
    );
  }, [query, modes, theme, onNewChat, onOpenSettings, onOpenArtifacts, onToggleTheme, onRunPrompt, onSetMode]);

  const grouped = useMemo(() => {
    const map = new Map<string, CommandItem[]>();
    items.forEach((it) => {
      if (!map.has(it.group)) map.set(it.group, []);
      map.get(it.group)!.push(it);
    });
    return Array.from(map.entries());
  }, [items]);

  const flat = items;

  useEffect(() => {
    setActiveIndex(0);
  }, [query]);

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "ArrowDown") {
      e.preventDefault();
      setActiveIndex((i) => Math.min(i + 1, flat.length - 1));
    } else if (e.key === "ArrowUp") {
      e.preventDefault();
      setActiveIndex((i) => Math.max(i - 1, 0));
    } else if (e.key === "Enter") {
      e.preventDefault();
      const item = flat[activeIndex];
      if (item) {
        item.action();
        onClose();
      }
    } else if (e.key === "Escape") {
      onClose();
    }
  };

  return (
    <AnimatePresence>
      {open && (
        <motion.div
          className="cmdk-overlay"
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          transition={{ duration: 0.16 }}
          onClick={onClose}
        >
          <motion.div
            className="cmdk-panel glass-strong"
            initial={{ opacity: 0, y: -16, scale: 0.98 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            exit={{ opacity: 0, y: -12, scale: 0.98 }}
            transition={{ duration: 0.18, ease: [0.16, 1, 0.3, 1] }}
            onClick={(e) => e.stopPropagation()}
          >
            <div className="cmdk-input-row">
              <SearchIcon size={17} className="cmdk-search-icon" />
              <input
                ref={inputRef}
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                onKeyDown={handleKeyDown}
                placeholder="Search actions, modes, or ask Meiko anything…"
                className="cmdk-input"
              />
              <span className="cmdk-kbd">esc</span>
            </div>
            <div className="cmdk-results">
              {flat.length === 0 && <div className="cmdk-empty">No matches</div>}
              {grouped.map(([group, groupItems]) => (
                <div key={group} className="cmdk-group">
                  <div className="cmdk-group-label">{group}</div>
                  {groupItems.map((it) => {
                    const idx = flat.indexOf(it);
                    return (
                      <button
                        key={it.id}
                        className={`cmdk-item ${idx === activeIndex ? "active" : ""}`}
                        onMouseEnter={() => setActiveIndex(idx)}
                        onClick={() => {
                          it.action();
                          onClose();
                        }}
                      >
                        <span className="cmdk-item-icon">{it.icon}</span>
                        <span className="cmdk-item-text">
                          <span className="cmdk-item-label">{it.label}</span>
                          {it.hint && <span className="cmdk-item-hint">{it.hint}</span>}
                        </span>
                        {idx === activeIndex && <CornerDownLeft size={13} className="cmdk-item-enter" />}
                      </button>
                    );
                  })}
                </div>
              ))}
            </div>
          </motion.div>
        </motion.div>
      )}
    </AnimatePresence>
  );
}
