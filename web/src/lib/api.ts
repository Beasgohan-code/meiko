/**
 * Meiko Web — API client
 * Talks to the FastAPI backend: streaming chat (SSE), providers, modes,
 * personas, connectors, settings, upload/download.
 */

export type AgentEventType =
  | "conversation_created"
  | "step"
  | "token"
  | "thinking"
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

// The backend base URL, in priority order:
//   1. VITE_BACKEND_URL baked in at build time (self-hosters/custom deploys).
//   2. Empty string when running on localhost (Vite's dev proxy in
//      vite.config.ts forwards /api -> the local backend).
//   3. Otherwise fall back to Meiko's own public Render backend, so the
//      hosted web app (e.g. the Vercel deploy) works out of the box even if
//      whoever deployed it forgot to set VITE_BACKEND_URL — previously a
//      missing env var here silently made every /api/* call hit Vercel's
//      own static host, which just served index.html back (a same-origin
//      "phantom 200" that looked like a working response but broke chat).
const PUBLIC_FALLBACK_BACKEND = "https://meiko.onrender.com";
function resolveBaseUrl(): string {
  const env = (import.meta as any).env;
  if (env?.VITE_BACKEND_URL) return env.VITE_BACKEND_URL.replace(/\/$/, "");
  // Under `vite dev`/`vite preview` (including a sandboxed dev-server
  // preview reached through a proxy host), always defer to the relative
  // `/api` path so vite.config.ts's own dev proxy forwards it — only a
  // genuine static production build (no dev server in front of it) should
  // ever fall back to the public backend below.
  if (env?.DEV) return "";
  return PUBLIC_FALLBACK_BACKEND;
}
const BASE_URL = resolveBaseUrl();


function headers(apiKey?: string) {
  const h: Record<string, string> = { "Content-Type": "application/json" };
  if (apiKey) h["X-API-Key"] = apiKey;
  return h;
}

export async function fetchProviders(): Promise<ProviderMeta[]> {
  const res = await fetch(`${BASE_URL}/api/providers`);
  return res.json();
}

// ---------------- Auth (optional GitHub sign-in) ----------------
export interface AuthUser {
  user_id: string;
  username: string;
  name?: string;
  email?: string;
  avatar_url?: string;
}

export async function fetchAuthConfig(): Promise<{ github_enabled: boolean }> {
  const res = await fetch(`${BASE_URL}/api/auth/config`);
  return res.json();
}

/** Full backend URL to send the browser to for the GitHub OAuth handshake. */
export function githubLoginUrl(): string {
  return `${BASE_URL || window.location.origin}/api/auth/github/login`;
}

export async function fetchMe(token: string): Promise<AuthUser | null> {
  const res = await fetch(`${BASE_URL}/api/auth/me`, {
    headers: { Authorization: `Bearer ${token}` },
  });
  if (!res.ok) return null;
  return res.json();
}

export async function logout(): Promise<void> {
  await fetch(`${BASE_URL}/api/auth/logout`, { method: "POST" });
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

export interface SkillDetail extends SkillMeta {
  body: string;
}

export async function fetchSkillDetail(skillId: string): Promise<SkillDetail> {
  const res = await fetch(`${BASE_URL}/api/skills/${encodeURIComponent(skillId)}`);
  if (!res.ok) throw new Error("Skill not found");
  return res.json();
}

export interface SkillDraft {
  name: string;
  description: string;
  triggers: string[];
  body: string;
  skill_id?: string;
}

export async function createSkill(draft: SkillDraft, apiKey?: string): Promise<SkillDetail> {
  const res = await fetch(`${BASE_URL}/api/skills`, {
    method: "POST",
    headers: headers(apiKey),
    body: JSON.stringify(draft),
  });
  if (!res.ok) throw new Error((await res.json().catch(() => ({})))?.detail || "Failed to create skill");
  return res.json();
}

export async function updateSkill(skillId: string, draft: SkillDraft, apiKey?: string): Promise<SkillDetail> {
  const res = await fetch(`${BASE_URL}/api/skills/${encodeURIComponent(skillId)}`, {
    method: "PUT",
    headers: headers(apiKey),
    body: JSON.stringify(draft),
  });
  if (!res.ok) throw new Error((await res.json().catch(() => ({})))?.detail || "Failed to update skill");
  return res.json();
}

export async function deleteSkill(skillId: string, apiKey?: string): Promise<void> {
  const res = await fetch(`${BASE_URL}/api/skills/${encodeURIComponent(skillId)}`, {
    method: "DELETE",
    headers: headers(apiKey),
  });
  if (!res.ok) throw new Error("Failed to delete skill");
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
  custom_base_url?: string;
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
  preview_url?: string;
  preview_kind?: "render" | "code";
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

/** Live-preview URL for a generated HTML artifact (vibe-coding mode) --
 * safe to drop straight into an <iframe src>. Appends the API key (if any)
 * as a query param since a bare <iframe> load can't attach headers. */
export function previewUrl(sessionId: string, relativePath: string) {
  const apiKey = localStorage.getItem("meiko_api_key") || "";
  const q = apiKey ? `?api_key=${encodeURIComponent(apiKey)}` : "";
  return `${BASE_URL}/api/preview/${encodeURIComponent(sessionId)}/${relativePath}${q}`;
}

/** Generalized read-only "code preview" link for any generated source file
 * (js/ts/css/json/md/py/yaml/...), extending the Vibe Coding live-preview
 * concept beyond just HTML. Same api_key-in-query trick as previewUrl so
 * it works as a bare, shareable link. */
export function codePreviewUrl(sessionId: string, relativePath: string) {
  const apiKey = localStorage.getItem("meiko_api_key") || "";
  const q = apiKey ? `?api_key=${encodeURIComponent(apiKey)}` : "";
  return `${BASE_URL}/api/preview-page/${encodeURIComponent(sessionId)}/${relativePath}${q}`;
}

/** Turns any of Meiko's own relative API paths (already returned by the
 * backend, e.g. a file's preview_url) into a fully-qualified, shareable
 * absolute URL — resolved against the current backend origin so it still
 * works when copied outside the app (a real "share this preview" link). */
export function absoluteUrl(relativeOrAbsolute: string): string {
  if (/^https?:\/\//i.test(relativeOrAbsolute)) return relativeOrAbsolute;
  const origin = BASE_URL || window.location.origin;
  return `${origin}${relativeOrAbsolute}`;
}

// ---------------- Dev Console (arena.ai/menus.ai-style live command runner) ----------------
export interface ConsoleRun {
  run_id: string;
  session_id: string;
  command: string;
  kind: "bash" | "python";
  status: "running" | "exited" | "killed" | "timeout" | "error";
  exit_code: number | null;
  started_at: number;
  finished_at: number | null;
}

export async function startConsoleRun(sessionId: string, command: string, kind: "bash" | "python", timeoutSeconds = 30): Promise<ConsoleRun> {
  const res = await fetch(`${BASE_URL}/api/console/run`, {
    method: "POST",
    headers: headers(),
    body: JSON.stringify({ session_id: sessionId, command, kind, timeout_seconds: timeoutSeconds }),
  });
  if (!res.ok) throw new Error((await res.json().catch(() => ({})))?.detail || "Failed to start run");
  return res.json();
}

export async function stopConsoleRun(runId: string): Promise<void> {
  await fetch(`${BASE_URL}/api/console/${runId}/stop`, { method: "POST", headers: headers() });
}

export async function fetchConsoleRuns(sessionId: string): Promise<ConsoleRun[]> {
  const res = await fetch(`${BASE_URL}/api/console/${encodeURIComponent(sessionId)}/runs`, { headers: headers() });
  if (!res.ok) return [];
  return res.json();
}

/** Live output socket for one run — pushes {event:"output", text, cursor}
 * chunks the instant they're produced, then a final {event:"exit", ...}.
 * Falls back to nothing special on failure; callers should also poll
 * /api/console/{run_id}/output if they want a resilience net. */
export function connectConsoleSocket(
  runId: string,
  onMessage: (msg: { event: "output" | "exit"; text?: string; cursor?: number; status?: string; exit_code?: number | null }) => void
): { close: () => void } {
  const wsBase = (BASE_URL || window.location.origin).replace(/^http/, "ws");
  const ws = new WebSocket(`${wsBase}/ws/console/${runId}`);
  ws.onmessage = (ev) => {
    try {
      onMessage(JSON.parse(ev.data));
    } catch {
      // ignore malformed frame
    }
  };
  return { close: () => ws.close() };
}

// ---------------- Tools Generator ----------------
export interface GeneratedTool {
  name: string;
  description: string;
  parameters: any;
  kind: "http" | "python";
  http_method?: string;
  http_url_template?: string;
  http_headers?: Record<string, string>;
  python_body?: string;
  created_at: number;
}

export interface GeneratedToolDraft {
  name: string;
  description: string;
  parameters?: any;
  kind: "http" | "python";
  http_method?: string;
  http_url_template?: string;
  http_headers?: Record<string, string>;
  python_body?: string;
}

export async function generateTool(draft: GeneratedToolDraft): Promise<GeneratedTool> {
  const res = await fetch(`${BASE_URL}/api/tools/generate`, {
    method: "POST",
    headers: headers(),
    body: JSON.stringify(draft),
  });
  if (!res.ok) throw new Error((await res.json().catch(() => ({})))?.detail || "Failed to generate tool");
  return res.json();
}

export async function fetchGeneratedTools(): Promise<GeneratedTool[]> {
  const res = await fetch(`${BASE_URL}/api/tools/generated`, { headers: headers() });
  if (!res.ok) return [];
  return res.json();
}

export async function deleteGeneratedTool(name: string): Promise<void> {
  await fetch(`${BASE_URL}/api/tools/generated/${encodeURIComponent(name)}`, { method: "DELETE", headers: headers() });
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
