import { useEffect, useRef, useState } from "react";
import {
  MessageCircle,
  Search,
  Code2,
  Cpu,
  Image as ImageIcon,
  Settings,
  Plus,
  Sparkles,
  Pin,
  Pencil,
  Trash2,
  Check,
  X,
} from "lucide-react";
import { animatePanelIn, animateStagger } from "../lib/animations";
import type { AgentModeMeta, PersonaMeta } from "../lib/api";
import {
  connectSyncSocket,
  deleteConversation,
  getConversationMessages,
  listConversations,
  pinConversation,
  renameConversation,
  searchConversations,
} from "../lib/api";
import { useMeikoStore } from "../lib/store";

const MODE_ICONS: Record<string, any> = {
  "message-circle": MessageCircle,
  search: Search,
  code: Code2,
  cpu: Cpu,
  image: ImageIcon,
};

interface ConversationSummary {
  id: string;
  title: string;
  pinned?: number;
  updated_at: number;
}

interface SidebarProps {
  modes: AgentModeMeta[];
  personas: PersonaMeta[];
  onOpenSettings: () => void;
  onNewChat: () => void;
  isOpen: boolean;
}

export default function Sidebar({ modes, personas, onOpenSettings, onNewChat, isOpen }: SidebarProps) {
  const { userId, conversationId, mode, setMode, personaId, setPersona, loadMessages } = useMeikoStore();
  const ref = useRef<HTMLDivElement>(null);
  const modeListRef = useRef<HTMLDivElement>(null);

  const [conversations, setConversations] = useState<ConversationSummary[]>([]);
  const [query, setQuery] = useState("");
  const [editingId, setEditingId] = useState<string | null>(null);
  const [editTitle, setEditTitle] = useState("");

  useEffect(() => {
    if (ref.current) animatePanelIn(ref.current, -24);
  }, []);

  useEffect(() => {
    if (modeListRef.current) animateStagger(modeListRef.current.children, 50);
  }, [modes]);

  const refresh = async () => {
    try {
      const data = query.trim() ? await searchConversations(userId, query.trim()) : await listConversations(userId);
      setConversations(data);
    } catch {
      // backend may be offline in preview; fail silently
    }
  };

  useEffect(() => {
    refresh();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [userId, conversationId]);

  useEffect(() => {
    const t = setTimeout(refresh, 250);
    return () => clearTimeout(t);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [query]);

  // Live cross-device sync: another tab, the Android/Flutter app, or Telegram
  // touching a conversation for this same account (see Settings → Sync)
  // refreshes this list immediately instead of waiting for a manual reload.
  useEffect(() => {
    const conn = connectSyncSocket(userId, (msg) => {
      if (
        msg.event === "conversation_created" ||
        msg.event === "conversation_updated" ||
        msg.event === "conversation_deleted" ||
        msg.event === "message_added"
      ) {
        refresh();
      }
    });
    return () => conn.close();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [userId]);

  const openConversation = async (id: string) => {
    try {
      const rows = await getConversationMessages(id);
      loadMessages(id, rows);
    } catch {
      // ignore
    }
  };

  const startRename = (c: ConversationSummary) => {
    setEditingId(c.id);
    setEditTitle(c.title || "Untitled");
  };

  const commitRename = async (id: string) => {
    const title = editTitle.trim();
    if (title) await renameConversation(id, title);
    setEditingId(null);
    refresh();
  };

  const togglePin = async (c: ConversationSummary) => {
    await pinConversation(c.id, !c.pinned);
    refresh();
  };

  const removeConversation = async (id: string) => {
    await deleteConversation(id);
    if (id === conversationId) onNewChat();
    refresh();
  };

  const sorted = [...conversations].sort((a, b) => (b.pinned || 0) - (a.pinned || 0) || b.updated_at - a.updated_at);

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

      <div className="history-section">
        <div className="section-label">History</div>
        <div className="history-search">
          <Search size={13} />
          <input
            placeholder="Search conversations…"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
          />
        </div>
        <div className="history-list">
          {sorted.map((c) => (
            <div key={c.id} className={`history-item ${conversationId === c.id ? "active" : ""}`}>
              {editingId === c.id ? (
                <div className="history-edit-row">
                  <input
                    autoFocus
                    value={editTitle}
                    onChange={(e) => setEditTitle(e.target.value)}
                    onKeyDown={(e) => e.key === "Enter" && commitRename(c.id)}
                  />
                  <button onClick={() => commitRename(c.id)} title="Save">
                    <Check size={13} />
                  </button>
                  <button onClick={() => setEditingId(null)} title="Cancel">
                    <X size={13} />
                  </button>
                </div>
              ) : (
                <>
                  <button className="history-title" onClick={() => openConversation(c.id)} title={c.title}>
                    {c.pinned ? <Pin size={11} className="pin-icon" /> : null}
                    <span>{c.title || "Untitled"}</span>
                  </button>
                  <div className="history-actions">
                    <button onClick={() => togglePin(c)} title={c.pinned ? "Unpin" : "Pin"}>
                      <Pin size={12} />
                    </button>
                    <button onClick={() => startRename(c)} title="Rename">
                      <Pencil size={12} />
                    </button>
                    <button onClick={() => removeConversation(c.id)} title="Delete">
                      <Trash2 size={12} />
                    </button>
                  </div>
                </>
              )}
            </div>
          ))}
          {sorted.length === 0 && <div className="history-empty">No conversations yet</div>}
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
