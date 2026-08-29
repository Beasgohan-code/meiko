import { useEffect, useRef } from "react";
import { MessageCircle, Search, Code2, Cpu, Image as ImageIcon, Settings, Plus, Sparkles } from "lucide-react";
import { animatePanelIn, animateStagger } from "../lib/animations";
import type { AgentModeMeta, PersonaMeta } from "../lib/api";
import { useMeikoStore } from "../lib/store";

const MODE_ICONS: Record<string, any> = {
  "message-circle": MessageCircle,
  search: Search,
  code: Code2,
  cpu: Cpu,
  image: ImageIcon,
};

interface SidebarProps {
  modes: AgentModeMeta[];
  personas: PersonaMeta[];
  onOpenSettings: () => void;
  onNewChat: () => void;
  isOpen: boolean;
}

export default function Sidebar({ modes, personas, onOpenSettings, onNewChat, isOpen }: SidebarProps) {
  const { mode, setMode, personaId, setPersona } = useMeikoStore();
  const ref = useRef<HTMLDivElement>(null);
  const modeListRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (ref.current) animatePanelIn(ref.current, -24);
  }, []);

  useEffect(() => {
    if (modeListRef.current) animateStagger(modeListRef.current.children, 50);
  }, [modes]);

  return (
    <aside className={`sidebar ${isOpen ? "open" : ""}`} ref={ref}>
      <div className="brand">
        <span className="brand-dot" />
        Meiko
      </div>

      <button className="new-chat-btn" onClick={onNewChat}>
        <Plus size={16} /> New chat
      </button>

      <div>
        <div className="section-label">Agent Mode</div>
        <div className="mode-list" ref={modeListRef}>
          {modes.map((m) => {
            const Icon = MODE_ICONS[m.icon] || Sparkles;
            return (
              <button
                key={m.id}
                className={`mode-item ${mode === m.id ? "active" : ""}`}
                onClick={() => setMode(m.id)}
              >
                <span className="name" style={{ display: "flex", alignItems: "center", gap: 7 }}>
                  <Icon size={14} /> {m.name}
                </span>
                <span className="desc">{m.description}</span>
              </button>
            );
          })}
        </div>
      </div>

      <div>
        <div className="section-label">Persona</div>
        <div className="persona-list">
          {personas.map((p) => (
            <button
              key={p.id}
              className={`persona-item ${personaId === p.id ? "active" : ""}`}
              onClick={() => setPersona(p.id)}
            >
              <span className="name">{p.name}</span>
              <span className="desc">{p.tagline}</span>
            </button>
          ))}
        </div>
      </div>

      <div className="sidebar-footer">
        <button className="settings-btn" onClick={onOpenSettings}>
          <Settings size={16} /> Settings & Connectors
        </button>
      </div>
    </aside>
  );
}
