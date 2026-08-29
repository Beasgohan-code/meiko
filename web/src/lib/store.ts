import { create } from "zustand";
import { v4 as uuidv4 } from "uuid";

export interface ToolTrace {
  id: string;
  name: string;
  arguments?: any;
  result?: string;
  status: "calling" | "done";
}

export interface ChatMessage {
  id: string;
  role: "user" | "assistant";
  content: string;
  tools: ToolTrace[];
  streaming?: boolean;
  error?: string;
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
  setMode: (mode: string) => void;
  setPersona: (personaId: string) => void;
  setProvider: (provider?: string, model?: string) => void;
  setConversationId: (id?: string) => void;
  addUserMessage: (content: string) => string;
  startAssistantMessage: () => string;
  appendToken: (id: string, text: string) => void;
  addToolCall: (assistantId: string, tool: ToolTrace) => void;
  updateToolResult: (assistantId: string, toolId: string, result: string) => void;
  finishAssistantMessage: (id: string, finalText?: string) => void;
  setError: (id: string, error: string) => void;
  setStreaming: (v: boolean) => void;
  resetConversation: () => void;
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

  setMode: (mode) => set({ mode }),
  setPersona: (personaId) => set({ personaId }),
  setProvider: (provider, model) => set({ provider, model }),
  setConversationId: (id) => set({ conversationId: id }),

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
}));
