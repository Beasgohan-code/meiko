/**
 * Meiko Web — API client
 * Talks to the FastAPI backend: streaming chat (SSE), providers, modes,
 * personas, connectors, settings, upload/download.
 */

export type AgentEventType =
  | "step"
  | "token"
  | "tool_call"
  | "tool_result"
  | "final"
  | "error"
  | "done";

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

export async function fetchPersonas(): Promise<PersonaMeta[]> {
  const res = await fetch(`${BASE_URL}/api/personas`);
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

export async function updateUserSettings(payload: {
  user_id: string;
  provider?: string;
  model?: string;
  persona?: string;
  api_keys?: Record<string, string>;
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
