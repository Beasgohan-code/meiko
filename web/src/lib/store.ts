import { create } from "zustand";
import { v4 as uuidv4 } from "uuid";

export interface ToolTrace {
  id: string;
  name: string;
  arguments?: any;
  result?: string;
  status: "calling" | "done";
}

export interface PlanTask {
  text: string;
  status: "pending" | "in_progress" | "done";
}

export interface Citation {
  url: string;
  via: string;
}

export interface RunInfo {
  provider?: string;
  model?: string;
  steps?: number;
  toolCalls?: number;
  elapsedSeconds?: number;
  providerSwitches?: number;
  tokensPerSecond?: number;
}

export interface ChatMessage {
  id: string;
  role: "user" | "assistant";
  content: string;
  tools: ToolTrace[];
  streaming?: boolean;
  error?: string;
  plan?: PlanTask[];
  citations?: Citation[];
  providerNotices?: string[];
  runInfo?: RunInfo;
  thinking?: string;
  isThinking?: boolean;
}

interface MeikoState {
  userId: string;
  sessionId: string;
  conversationId?: string;
  mode: string;
  personaId: string;
  provider?: string;
  model?: string;
  messages: ChatMessage[];
  isStreaming: boolean;
  theme: "dark" | "light";
  setTheme: (theme: "dark" | "light") => void;
  toggleTheme: () => void;
  setMode: (mode: string) => void;
  setPersona: (personaId: string) => void;
  setProvider: (provider?: string, model?: string) => void;
  setConversationId: (id?: string) => void;
  setUserId: (id: string) => void;
  addUserMessage: (content: string) => string;
  startAssistantMessage: () => string;
  appendToken: (id: string, text: string) => void;
  appendThinking: (id: string, text: string) => void;
  setThinkingDone: (id: string) => void;
  addToolCall: (assistantId: string, tool: ToolTrace) => void;
  updateToolResult: (assistantId: string, toolId: string, result: string) => void;
  finishAssistantMessage: (id: string, finalText?: string) => void;
  setError: (id: string, error: string) => void;
  setStreaming: (v: boolean) => void;
  resetConversation: () => void;
  updatePlan: (assistantId: string, tasks: PlanTask[]) => void;
  setCitations: (assistantId: string, citations: Citation[]) => void;
  addProviderNotice: (assistantId: string, notice: string) => void;
  setRunInfo: (assistantId: string, info: RunInfo) => void;
  loadMessages: (conversationId: string, rows: { role: string; content: string }[]) => void;
}

export const useMeikoStore = create<MeikoState>((set, get) => ({
  userId: localStorage.getItem("meiko_user_id") || (() => {
    const id = "user-" + uuidv4().slice(0, 8);
    localStorage.setItem("meiko_user_id", id);
    return id;
  })(),
  sessionId: uuidv4(),
  conversationId: undefined,
  mode: "autonomous",
  personaId: "default",
  provider: undefined,
  model: undefined,
  messages: [],
  isStreaming: false,
  theme: (localStorage.getItem("meiko_theme") as "dark" | "light") || "dark",

  setTheme: (theme) => {
    localStorage.setItem("meiko_theme", theme);
    document.documentElement.setAttribute("data-theme", theme);
    set({ theme });
  },
  toggleTheme: () => {
    const next = get().theme === "dark" ? "light" : "dark";
    localStorage.setItem("meiko_theme", next);
    document.documentElement.setAttribute("data-theme", next);
    set({ theme: next });
  },

  setMode: (mode) => set({ mode }),
  setPersona: (personaId) => set({ personaId }),
  setProvider: (provider, model) => set({ provider, model }),
  setConversationId: (id) => set({ conversationId: id }),
  setUserId: (id) => {
    localStorage.setItem("meiko_user_id", id);
    set({ userId: id, conversationId: undefined, messages: [] });
  },

  addUserMessage: (content) => {
    const id = uuidv4();
    set((s) => ({ messages: [...s.messages, { id, role: "user", content, tools: [] }] }));
    return id;
  },

  startAssistantMessage: () => {
    const id = uuidv4();
    set((s) => ({
      messages: [...s.messages, { id, role: "assistant", content: "", tools: [], streaming: true }],
    }));
    return id;
  },

  appendToken: (id, text) =>
    set((s) => ({
      messages: s.messages.map((m) => (m.id === id ? { ...m, content: m.content + text } : m)),
    })),

  appendThinking: (id, text) =>
    set((s) => ({
      messages: s.messages.map((m) =>
        m.id === id ? { ...m, thinking: (m.thinking || "") + text, isThinking: true } : m
      ),
    })),

  setThinkingDone: (id) =>
    set((s) => ({
      messages: s.messages.map((m) => (m.id === id ? { ...m, isThinking: false } : m)),
    })),

  addToolCall: (assistantId, tool) =>
    set((s) => ({
      messages: s.messages.map((m) =>
        m.id === assistantId ? { ...m, tools: [...m.tools, tool] } : m
      ),
    })),

  updateToolResult: (assistantId, toolId, result) =>
    set((s) => ({
      messages: s.messages.map((m) =>
        m.id === assistantId
          ? {
              ...m,
              tools: m.tools.map((t) => (t.id === toolId ? { ...t, result, status: "done" } : t)),
            }
          : m
      ),
    })),

  finishAssistantMessage: (id, finalText) =>
    set((s) => ({
      messages: s.messages.map((m) =>
        m.id === id
          ? { ...m, streaming: false, content: finalText !== undefined && finalText.length > 0 ? finalText : m.content }
          : m
      ),
    })),

  setError: (id, error) =>
    set((s) => ({
      messages: s.messages.map((m) => (m.id === id ? { ...m, streaming: false, error } : m)),
    })),

  setStreaming: (v) => set({ isStreaming: v }),

  resetConversation: () => set({ messages: [], conversationId: undefined, sessionId: uuidv4() }),

  updatePlan: (assistantId, tasks) =>
    set((s) => ({
      messages: s.messages.map((m) => (m.id === assistantId ? { ...m, plan: tasks } : m)),
    })),

  setCitations: (assistantId, citations) =>
    set((s) => ({
      messages: s.messages.map((m) => (m.id === assistantId ? { ...m, citations } : m)),
    })),

  addProviderNotice: (assistantId, notice) =>
    set((s) => ({
      messages: s.messages.map((m) =>
        m.id === assistantId ? { ...m, providerNotices: [...(m.providerNotices || []), notice] } : m
      ),
    })),

  setRunInfo: (assistantId, info) =>
    set((s) => ({
      messages: s.messages.map((m) => (m.id === assistantId ? { ...m, runInfo: info } : m)),
    })),

  loadMessages: (conversationId, rows) =>
    set({
      conversationId,
      sessionId: conversationId,
      messages: rows
        .filter((r) => r.role === "user" || r.role === "assistant")
        .map((r) => ({
          id: uuidv4(),
          role: r.role as "user" | "assistant",
          content: r.content,
          tools: [],
        })),
    }),
}));
