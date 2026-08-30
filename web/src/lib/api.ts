/**
 * Meiko Web — API client
 * Talks to the FastAPI backend: streaming chat (SSE), providers, modes,
 * personas, connectors, settings, upload/download.
 */

export type AgentEventType =
  | "conversation_created"
  | "step"
  | "token"
  | "tool_call"
  | "tool_result"
  | "plan_update"
  | "citations"
  | "provider_switch"
  | "final"
  | "error"
  | "done";

export interface PlanTask {
  text: string;
  status: "pending" | "in_progress" | "done";
}

export interface Citation {
  url: string;
  via: string;
}

export interface AgentEvent {
  type: AgentEventType;
  [key: string]: any;
}

export interface ProviderMeta {
  id: string;
  display_name: string;
  default_base_url: string;
  default_model: string;
  requires_key: boolean;
  free_tier: boolean;
  key_help_url: string;
  description: string;
}

export interface AgentModeMeta {
  id: string;
  name: string;
  description: string;
  icon: string;
  max_steps: number;
}

export interface PersonaMeta {
  id: string;
  name: string;
  tagline: string;
}

export interface ConnectorMeta {
  id: string;
  name: string;
  description: string;
  enabled: boolean;
  requires_key: boolean;
  actions: string[];
}

export interface ModelMeta {
  id: string;
  display_name: string;
  family: string;
  reasoning: boolean;
  vision: boolean;
  context_window: string;
  good_for: string[];
  tag: string;
}

export interface MemoryFact {
  id: string;
  user_id: string;
  fact: string;
  created_at: number;
}

const BASE_URL = (import.meta as any).env?.VITE_BACKEND_URL || "";

function headers(apiKey?: string) {
  const h: Record<string, string> = { "Content-Type": "application/json" };
  if (apiKey) h["X-API-Key"] = apiKey;
  return h;
}

export async function fetchProviders(): Promise<ProviderMeta[]> {
  const res = await fetch(`${BASE_URL}/api/providers`);
  return res.json();
}

export async function fetchModes(): Promise<AgentModeMeta[]> {
  const res = await fetch(`${BASE_URL}/api/modes`);
  return res.json();
}

export async function fetchModels(provider: string): Promise<ModelMeta[]> {
  const res = await fetch(`${BASE_URL}/api/models?provider=${encodeURIComponent(provider)}`);
  return res.json();
}

export async function fetchMemories(userId: string, query?: string): Promise<MemoryFact[]> {
  const q = query && query.trim() ? `&q=${encodeURIComponent(query.trim())}` : "";
  const res = await fetch(`${BASE_URL}/api/memories?user_id=${encodeURIComponent(userId)}${q}`, { headers: headers() });
  return res.json();
}

export async function deleteMemory(memoryId: string) {
  const res = await fetch(`${BASE_URL}/api/memories/${memoryId}`, { method: "DELETE", headers: headers() });
  return res.json();
}

export async function clearMemories(userId: string) {
  const res = await fetch(`${BASE_URL}/api/memories?user_id=${encodeURIComponent(userId)}`, {
    method: "DELETE",
    headers: headers(),
  });
  return res.json();
}

export async function fetchPersonas(): Promise<PersonaMeta[]> {
  const res = await fetch(`${BASE_URL}/api/personas`);
  return res.json();
}

export interface SkillMeta {
  id: string;
  name: string;
  description: string;
  triggers: string[];
}

export async function fetchSkills(): Promise<SkillMeta[]> {
  const res = await fetch(`${BASE_URL}/api/skills`);
  return res.json();
}

export async function fetchConnectors(): Promise<ConnectorMeta[]> {
  const res = await fetch(`${BASE_URL}/api/connectors`);
  return res.json();
}

export async function toggleConnector(id: string, enabled: boolean) {
  const res = await fetch(`${BASE_URL}/api/connectors/${id}/toggle`, {
    method: "POST",
    headers: headers(),
    body: JSON.stringify({ enabled }),
  });
  return res.json();
}

export async function getUserSettings(userId: string) {
  const res = await fetch(`${BASE_URL}/api/settings?user_id=${encodeURIComponent(userId)}`);
  return res.json();
}

// ---------------- Cross-device sync ----------------
// Every client already shares the backend's data model via `user_id`; these
// helpers make it possible for a human to move that `user_id` between
// devices with a short 6-character code instead of copy-pasting a UUID, and
// to react live when another device changes something.
export interface PairingCode {
  code: string;
  expires_in: number;
}

export async function createPairingCode(userId: string): Promise<PairingCode> {
  const res = await fetch(`${BASE_URL}/api/sync/pair`, {
    method: "POST",
    headers: { "Content-Type": "application/json", ...headers() },
    body: JSON.stringify({ user_id: userId }),
  });
  if (!res.ok) throw new Error("Could not create a pairing code.");
  return res.json();
}

export async function claimPairingCode(code: string): Promise<{ user_id: string }> {
  const res = await fetch(`${BASE_URL}/api/sync/claim`, {
    method: "POST",
    headers: { "Content-Type": "application/json", ...headers() },
    body: JSON.stringify({ code }),
  });
  if (!res.ok) throw new Error("That code is invalid or has expired. Codes last 10 minutes.");
  return res.json();
}

export async function getSyncStatus(userId: string): Promise<{ connected_devices: number }> {
  const res = await fetch(`${BASE_URL}/api/sync/status?user_id=${encodeURIComponent(userId)}`);
  return res.json();
}

export type SyncEventType = "message_added" | "settings_updated" | "memory_updated" | "conversation_updated" | "conversation_created" | "conversation_deleted";

export interface SyncMessage {
  event: SyncEventType;
  data: Record<string, any>;
  ts: number;
}

/**
 * Opens a live WebSocket to /ws/sync/{userId} and calls `onMessage` for every
 * push from the backend (fired whenever *any* device sharing this user_id
 * changes a conversation/setting/memory). Auto-reconnects with backoff so a
 * flaky connection (mobile network, laptop sleep) doesn't permanently kill
 * live sync — call the returned `close()` to tear it down (e.g. on unmount).
 */
export function connectSyncSocket(userId: string, onMessage: (msg: SyncMessage) => void): { close: () => void } {
  let socket: WebSocket | null = null;
  let closed = false;
  let retryDelay = 1000;

  const wsBase = (BASE_URL || window.location.origin).replace(/^http/, "ws");

  function connect() {
    if (closed) return;
    try {
      socket = new WebSocket(`${wsBase}/ws/sync/${encodeURIComponent(userId)}`);
    } catch {
      scheduleReconnect();
      return;
    }
    socket.onopen = () => {
      retryDelay = 1000;
    };
    socket.onmessage = (ev) => {
      try {
        onMessage(JSON.parse(ev.data));
      } catch {
        /* ignore malformed frames */
      }
    };
    socket.onclose = scheduleReconnect;
    socket.onerror = () => socket?.close();
  }

  function scheduleReconnect() {
    if (closed) return;
    setTimeout(connect, retryDelay);
    retryDelay = Math.min(retryDelay * 1.7, 20000);
  }

  connect();

  return {
    close: () => {
      closed = true;
      socket?.close();
    },
  };
}

export async function updateUserSettings(payload: {
  user_id: string;
  provider?: string;
  model?: string;
  persona?: string;
  api_keys?: Record<string, string>;
  ui_language?: string;
}) {
  const res = await fetch(`${BASE_URL}/api/settings`, {
    method: "POST",
    headers: headers(),
    body: JSON.stringify(payload),
  });
  return res.json();
}

export async function listConversations(userId: string) {
  const res = await fetch(`${BASE_URL}/api/conversations?user_id=${encodeURIComponent(userId)}`);
  return res.json();
}

export async function createConversation(userId: string, title = "") {
  const res = await fetch(`${BASE_URL}/api/conversations`, {
    method: "POST",
    headers: headers(),
    body: JSON.stringify({ user_id: userId, title }),
  });
  return res.json();
}

export async function getConversationMessages(conversationId: string) {
  const res = await fetch(`${BASE_URL}/api/conversations/${conversationId}/messages`);
  return res.json();
}

export async function renameConversation(conversationId: string, title: string) {
  const res = await fetch(`${BASE_URL}/api/conversations/${conversationId}`, {
    method: "PATCH",
    headers: headers(),
    body: JSON.stringify({ title }),
  });
  return res.json();
}

export async function deleteConversation(conversationId: string) {
  const res = await fetch(`${BASE_URL}/api/conversations/${conversationId}`, {
    method: "DELETE",
    headers: headers(),
  });
  return res.json();
}

export async function pinConversation(conversationId: string, pinned: boolean) {
  const res = await fetch(`${BASE_URL}/api/conversations/${conversationId}/pin?pinned=${pinned}`, {
    method: "POST",
    headers: headers(),
  });
  return res.json();
}

export async function searchConversations(userId: string, query: string) {
  const res = await fetch(
    `${BASE_URL}/api/conversations/search?user_id=${encodeURIComponent(userId)}&q=${encodeURIComponent(query)}`
  );
  return res.json();
}

export async function getUsageSummary(userId: string, days = 30) {
  const res = await fetch(`${BASE_URL}/api/usage?user_id=${encodeURIComponent(userId)}&days=${days}`);
  return res.json();
}

// ---------------- System health (OmniRoute Health Dashboard-inspired) ----------------
export interface SystemStatus {
  status: "ok" | "degraded";
  app: string;
  version: string;
  uptime_seconds: number;
  store: { backend: "sqlite" | "postgresql"; reachable: boolean; error: string | null };
  providers: { total: number; free_tier: number; keyless: number };
  connectors: { total: number; enabled: number; tool_count: number };
  skills: number;
  default_provider: string;
  embeddings_enabled: boolean;
}

export async function fetchSystemStatus(): Promise<SystemStatus> {
  const res = await fetch(`${BASE_URL}/api/system/status`, { headers: headers() });
  if (!res.ok) throw new Error("Could not reach system status endpoint");
  return res.json();
}

// ---------------- Artifacts / workspace files (Open Design artifact-tree-inspired) ----------------
export interface WorkspaceFile {
  name: string;
  kind: "workspace" | "exports";
  size_bytes: number;
  modified_at: number;
  download_url: string;
}

export async function fetchWorkspaceFiles(sessionId: string): Promise<WorkspaceFile[]> {
  const res = await fetch(`${BASE_URL}/api/workspace/${encodeURIComponent(sessionId)}/files`, { headers: headers() });
  if (!res.ok) return [];
  return res.json();
}

export async function uploadFile(sessionId: string, file: File) {
  const form = new FormData();
  form.append("file", file);
  const res = await fetch(`${BASE_URL}/api/upload?session_id=${encodeURIComponent(sessionId)}`, {
    method: "POST",
    body: form,
  });
  return res.json();
}

export function downloadUrl(sessionId: string, filename: string) {
  return `${BASE_URL}/api/download/${sessionId}/${filename}`;
}

export interface ChatStreamParams {
  userId: string;
  message: string;
  mode: string;
  conversationId?: string;
  sessionId?: string;
  provider?: string;
  model?: string;
  personaId?: string;
  imagePaths?: string[];
  enableFallback?: boolean;
  uiLanguage?: string;
}

/**
 * Streams a chat turn from Meiko via SSE (fetch + ReadableStream, since
 * EventSource doesn't support POST bodies). Calls `onEvent` for each
 * structured AgentEvent as it arrives.
 */
export async function streamChat(
  params: ChatStreamParams,
  onEvent: (event: AgentEvent) => void,
  signal?: AbortSignal
): Promise<void> {
  const res = await fetch(`${BASE_URL}/api/chat/stream`, {
    method: "POST",
    headers: headers(),
    signal,
    body: JSON.stringify({
      user_id: params.userId,
      message: params.message,
      mode: params.mode,
      conversation_id: params.conversationId,
      session_id: params.sessionId,
      provider: params.provider,
      model: params.model,
      persona_id: params.personaId,
      image_paths: params.imagePaths,
      enable_fallback: params.enableFallback ?? true,
      ui_language: params.uiLanguage,
    }),
  });

  if (!res.body) throw new Error("No response body for stream");
  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    const parts = buffer.split("\n\n");
    buffer = parts.pop() || "";
    for (const part of parts) {
      const line = part.trim();
      if (!line.startsWith("data:")) continue;
      const data = line.slice(5).trim();
      if (!data) continue;
      try {
        onEvent(JSON.parse(data));
      } catch {
        // ignore malformed chunk
      }
    }
  }
}
