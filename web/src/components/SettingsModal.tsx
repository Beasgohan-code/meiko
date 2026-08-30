import { useEffect, useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import {
  X,
  Github,
  Sparkles,
  Brain,
  Trash2,
  Copy,
  Check,
  Link2,
  Smartphone,
  Activity,
  BarChart3,
  Database,
  Puzzle,
  Cpu,
  SlidersHorizontal,
  UserCircle2,
} from "lucide-react";
import {
  ConnectorMeta,
  MemoryFact,
  ModelMeta,
  ProviderMeta,
  SkillMeta,
  SystemStatus,
  claimPairingCode,
  clearMemories,
  connectSyncSocket,
  createPairingCode,
  deleteMemory,
  fetchConnectors,
  fetchMemories,
  fetchModels,
  fetchProviders,
  fetchSkills,
  fetchSystemStatus,
  getSyncStatus,
  getUsageSummary,
  getUserSettings,
  toggleConnector,
  updateUserSettings,
} from "../lib/api";
import { useMeikoStore } from "../lib/store";
import { useI18n, SUPPORTED_LANGUAGES } from "../lib/i18n";

interface Props {
  onClose: () => void;
}

const MODEL_TAG_LABEL: Record<string, string> = {
  flagship: "🏆 Flagship",
  fast: "⚡ Fast",
  coding: "💻 Coding",
  vision: "👁 Vision",
  default: "⭐ Default",
};

export default function SettingsModal({ onClose }: Props) {
  const { userId, provider, model, setProvider, setUserId } = useMeikoStore();
  const { t } = useI18n();
  const [tab, setTab] = useState<
    "providers" | "connectors" | "skills" | "memory" | "persona" | "sync" | "usage" | "health"
  >("providers");
  const [providers, setProviders] = useState<ProviderMeta[]>([]);
  const [models, setModels] = useState<ModelMeta[]>([]);
  const [connectors, setConnectors] = useState<ConnectorMeta[]>([]);
  const [skills, setSkills] = useState<SkillMeta[]>([]);
  const [memories, setMemories] = useState<MemoryFact[]>([]);
  const [memorySearch, setMemorySearch] = useState("");
  const [keys, setKeys] = useState<Record<string, string>>({});
  const [activeProvider, setActiveProvider] = useState(provider || "nvidia");
  const [activeModel, setActiveModel] = useState(model || "");
  const [replyLanguage, setReplyLanguage] = useState("en");
  const [customPersona, setCustomPersona] = useState("");
  const [saveStatus, setSaveStatus] = useState<string>("");
  const [githubStatus, setGithubStatus] = useState<string>("");
  const [pairingCode, setPairingCode] = useState<string>("");
  const [pairingExpiresAt, setPairingExpiresAt] = useState<number | null>(null);
  const [claimInput, setClaimInput] = useState("");
  const [syncStatus, setSyncStatus] = useState<string>("");
  const [connectedDevices, setConnectedDevices] = useState(0);
  const [copied, setCopied] = useState(false);
  const [usage, setUsage] = useState<any>(null);
  const [usageDays, setUsageDays] = useState(30);
  const [systemStatus, setSystemStatus] = useState<SystemStatus | null>(null);
  const [systemStatusError, setSystemStatusError] = useState<string>("");

  useEffect(() => {
    fetchProviders().then(setProviders);
    fetchConnectors().then(setConnectors);
    fetchSkills().then(setSkills);
    fetchMemories(userId).then(setMemories).catch(() => {});
    getUserSettings(userId).then((s) => {
      if (s.provider) setActiveProvider(s.provider);
      if (s.model) setActiveModel(s.model);
      if (s.persona) setCustomPersona(s.persona);
      if (s.ui_language) setReplyLanguage(s.ui_language);
    });
    getSyncStatus(userId).then((s) => setConnectedDevices(s.connected_devices)).catch(() => {});
  }, [userId]);

  useEffect(() => {
    fetchModels(activeProvider).then(setModels);
  }, [activeProvider]);

  useEffect(() => {
    if (tab === "usage") {
      getUsageSummary(userId, usageDays).then(setUsage).catch(() => setUsage(null));
    }
    if (tab === "health") {
      fetchSystemStatus()
        .then((s) => {
          setSystemStatus(s);
          setSystemStatusError("");
        })
        .catch(() => setSystemStatusError("Could not reach the backend's system status endpoint."));
    }
  }, [tab, userId, usageDays]);

  // Live sync: reflect settings/memory changes made from another linked
  // device (or the pairing count changing) while this modal is open.
  useEffect(() => {
    const conn = connectSyncSocket(userId, (msg) => {
      if (msg.event === "settings_updated") {
        getUserSettings(userId).then((s) => {
          if (s.provider) setActiveProvider(s.provider);
          if (s.model) setActiveModel(s.model);
          if (s.persona) setCustomPersona(s.persona);
          if (s.ui_language) setReplyLanguage(s.ui_language);
        });
      } else if (msg.event === "memory_updated") {
        fetchMemories(userId).then(setMemories).catch(() => {});
      }
      // Any live event means at least one other device is connected —
      // refresh the "N devices online" hint opportunistically.
      getSyncStatus(userId).then((s) => setConnectedDevices(s.connected_devices)).catch(() => {});
    });
    return () => conn.close();
  }, [userId]);

  const handleMemorySearch = (value: string) => {
    setMemorySearch(value);
    fetchMemories(userId, value).then(setMemories).catch(() => {});
  };

  const handleDeleteMemory = async (id: string) => {
    await deleteMemory(id);
    setMemories((prev) => prev.filter((m) => m.id !== id));
  };

  const handleClearMemories = async () => {
    await clearMemories(userId);
    setMemories([]);
  };

  const saveKey = async (providerId: string, key: string) => {
    setKeys((prev) => ({ ...prev, [providerId]: key }));
  };

  const persistSettings = async () => {
    setSaveStatus("Saving…");
    await updateUserSettings({
      user_id: userId,
      provider: activeProvider,
      model: activeModel || undefined,
      persona: customPersona,
      api_keys: keys,
      ui_language: replyLanguage,
    });
    setProvider(activeProvider, activeModel || undefined);
    setSaveStatus("Saved ✓");
    setTimeout(() => setSaveStatus(""), 1500);
  };

  const saveGithubToken = async () => {
    setGithubStatus("Saving…");
    await updateUserSettings({
      user_id: userId,
      api_keys: { github: keys.github || "" },
    });
    setGithubStatus("Saved ✓ — GitHub read/write tools are now active");
    setTimeout(() => setGithubStatus(""), 2500);
  };

  const handleToggleConnector = async (c: ConnectorMeta) => {
    await toggleConnector(c.id, !c.enabled);
    setConnectors((prev) => prev.map((x) => (x.id === c.id ? { ...x, enabled: !x.enabled } : x)));
  };

  const handleCreatePairingCode = async () => {
    setSyncStatus("");
    try {
      const res = await createPairingCode(userId);
      setPairingCode(res.code);
      setPairingExpiresAt(Date.now() + res.expires_in * 1000);
    } catch {
      setSyncStatus("Could not create a pairing code — is the backend reachable?");
    }
  };

  const handleCopyCode = async () => {
    if (!pairingCode) return;
    try {
      await navigator.clipboard.writeText(pairingCode);
      setCopied(true);
      setTimeout(() => setCopied(false), 1500);
    } catch {
      /* clipboard permission denied — user can still select+copy manually */
    }
  };

  const handleClaimCode = async () => {
    setSyncStatus("Linking…");
    try {
      const res = await claimPairingCode(claimInput.trim());
      setUserId(res.user_id);
      setSyncStatus("Linked! This device now shares conversations, settings, and memory with the other one. 🎉");
      setClaimInput("");
      const status = await getSyncStatus(res.user_id);
      setConnectedDevices(status.connected_devices);
    } catch (e: any) {
      setSyncStatus(e?.message || "That code is invalid or has expired.");
    }
  };

  const TABS: { id: typeof tab; label: string; icon: React.ReactNode }[] = [
    { id: "providers", label: "Model Providers", icon: <SlidersHorizontal size={15} /> },
    { id: "connectors", label: "Connectors", icon: <Puzzle size={15} /> },
    { id: "skills", label: t("skills"), icon: <Sparkles size={15} /> },
    { id: "memory", label: t("memory"), icon: <Brain size={15} /> },
    { id: "persona", label: t("persona"), icon: <UserCircle2 size={15} /> },
    { id: "sync", label: t("sync"), icon: <Smartphone size={15} /> },
    { id: "usage", label: "Usage", icon: <BarChart3 size={15} /> },
    { id: "health", label: "Health", icon: <Activity size={15} /> },
  ];

  return (
    <motion.div
      className="modal-overlay"
      onClick={onClose}
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      exit={{ opacity: 0 }}
      transition={{ duration: 0.18 }}
    >
      <motion.div
        className="modal-panel settings-shell"
        onClick={(e) => e.stopPropagation()}
        initial={{ opacity: 0, y: 18, scale: 0.97 }}
        animate={{ opacity: 1, y: 0, scale: 1 }}
        exit={{ opacity: 0, y: 14, scale: 0.97 }}
        transition={{ duration: 0.22, ease: [0.16, 1, 0.3, 1] }}
      >
        <nav className="settings-nav">
          <div className="settings-nav-title">Settings</div>
          {TABS.map((tb) => (
            <button
              key={tb.id}
              className={`settings-nav-item ${tab === tb.id ? "active" : ""}`}
              onClick={() => setTab(tb.id)}
            >
              {tb.icon}
              <span>{tb.label}</span>
              {tab === tb.id && <motion.span layoutId="settings-nav-glow" className="settings-nav-glow" />}
            </button>
          ))}
        </nav>

        <div className="settings-content">
        <div className="modal-header">
          <h2>{TABS.find((tb) => tb.id === tab)?.label}</h2>
          <button className="close-btn" onClick={onClose}>
            <X size={20} />
          </button>
        </div>

        <AnimatePresence mode="wait">
        <motion.div
          key={tab}
          initial={{ opacity: 0, x: 8 }}
          animate={{ opacity: 1, x: 0 }}
          exit={{ opacity: 0, x: -8 }}
          transition={{ duration: 0.15 }}
        >
        {tab === "providers" && (
          <div className="provider-card-list">
            <p className="field-hint" style={{ marginBottom: 4 }}>
              Pick your default model provider and paste a free API key. NVIDIA NIM, Gemini, OpenRouter, Groq,
              Cerebras, Hugging Face and Mistral all offer generous free tiers.
            </p>
            {providers.map((p) => (
              <div className="provider-card" key={p.id}>
                <div className="row">
                  <label style={{ display: "flex", alignItems: "center", gap: 8 }}>
                    <input
                      type="radio"
                      name="provider"
                      checked={activeProvider === p.id}
                      onChange={() => setActiveProvider(p.id)}
                    />
                    <span className="name">{p.display_name}</span>
                  </label>
                  {p.free_tier && <span className="free-badge">FREE</span>}
                </div>
                <div className="desc">{p.description}</div>
                {p.requires_key && (
                  <input
                    type="password"
                    placeholder={`${p.display_name} API key`}
                    defaultValue={keys[p.id] || ""}
                    onChange={(e) => saveKey(p.id, e.target.value)}
                  />
                )}
                <div className="field-hint">
                  <a href={p.key_help_url} target="_blank" rel="noreferrer">
                    Get a free API key →
                  </a>
                </div>
              </div>
            ))}

            <div className="provider-card" style={{ marginTop: 10 }}>
              <div className="row">
                <span className="name" style={{ display: "flex", alignItems: "center", gap: 8 }}>
                  <Brain size={16} /> {t("pickModel")} — {activeProvider}
                </span>
              </div>
              <div className="desc">
                NVIDIA alone offers 20+ free curated models (DeepSeek, Kimi, GLM, Qwen, Llama, Mistral, Nemotron…).
                Pick one that fits your task, or leave the default for a balanced general-purpose choice.
              </div>
              <div className="model-grid">
                {models.map((m) => (
                  <button
                    key={m.id}
                    className={`model-card ${activeModel === m.id ? "active" : ""}`}
                    onClick={() => setActiveModel(m.id)}
                    title={m.id}
                  >
                    <div className="model-card-name">{m.display_name}</div>
                    <div className="model-card-meta">
                      {m.tag && <span className="model-badge">{MODEL_TAG_LABEL[m.tag] || m.tag}</span>}
                      {m.reasoning && <span className="model-badge">🧠 {t("reasoning")}</span>}
                      {m.vision && <span className="model-badge">👁 {t("vision")}</span>}
                      {m.context_window && <span className="model-badge">{m.context_window} ctx</span>}
                    </div>
                    {m.good_for?.length > 0 && <div className="model-card-good-for">{m.good_for.join(" · ")}</div>}
                  </button>
                ))}
                {models.length === 0 && <div className="field-hint">Loading models…</div>}
              </div>
            </div>

            <div className="provider-card" style={{ marginTop: 10 }}>
              <div className="row">
                <span className="name">{t("replyLanguage")}</span>
              </div>
              <div className="desc">{t("replyLanguageHelp")}</div>
              <select value={replyLanguage} onChange={(e) => setReplyLanguage(e.target.value)} className="lang-select">
                {SUPPORTED_LANGUAGES.map((l) => (
                  <option key={l.code} value={l.code}>
                    {l.flag} {l.label}
                  </option>
                ))}
              </select>
            </div>

            <button className="new-chat-btn" style={{ justifyContent: "center", marginTop: 12 }} onClick={persistSettings}>
              {saveStatus || "Save provider settings"}
            </button>
          </div>
        )}

        {tab === "connectors" && (
          <div>
            <p className="field-hint" style={{ marginBottom: 10 }}>
              Connectors give Meiko extra tools (like Claude Connectors / MCP). Toggle them on/off — Meiko will
              automatically use enabled ones when helpful.
            </p>

            <div className="provider-card" style={{ marginBottom: 14 }}>
              <div className="row">
                <span className="name" style={{ display: "flex", alignItems: "center", gap: 8 }}>
                  <Github size={16} /> GitHub (read + write)
                </span>
              </div>
              <div className="desc">
                Add a Personal Access Token with <code>repo</code> scope to let Meiko read files, commit changes,
                open pull requests, and create issues in your repos — not just search public code.
              </div>
              <input
                type="password"
                placeholder="ghp_… (Personal Access Token)"
                defaultValue={keys.github || ""}
                onChange={(e) => saveKey("github", e.target.value)}
              />
              <div className="field-hint">
                <a href="https://github.com/settings/tokens/new?scopes=repo&description=Meiko%20Agent" target="_blank" rel="noreferrer">
                  Create a token on GitHub →
                </a>
              </div>
              <button className="new-chat-btn" style={{ justifyContent: "center", marginTop: 8 }} onClick={saveGithubToken}>
                {githubStatus || "Save GitHub token"}
              </button>
            </div>

            <div className="provider-card" style={{ marginBottom: 14 }}>
              <div className="row">
                <span className="name" style={{ display: "flex", alignItems: "center", gap: 8 }}>
                  ▲ Vercel
                </span>
              </div>
              <div className="desc">
                Add a Vercel personal access token to let Meiko list your projects, check deployment status, trigger
                redeploys, and manage environment variables — handy after Vibe Coding builds something you want to ship.
              </div>
              <input
                type="password"
                placeholder="Vercel personal access token"
                defaultValue={keys.vercel || ""}
                onChange={(e) => saveKey("vercel", e.target.value)}
              />
              <div className="field-hint">
                <a href="https://vercel.com/account/tokens" target="_blank" rel="noreferrer">
                  Create a token on Vercel →
                </a>
              </div>
              <button className="new-chat-btn" style={{ justifyContent: "center", marginTop: 8 }} onClick={persistSettings}>
                {saveStatus || "Save Vercel token"}
              </button>
            </div>

            <AnimatePresence>
            {connectors.map((c) => (
              <motion.div
                className="connector-row"
                key={c.id}
                layout
                initial={{ opacity: 0, y: 6 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ duration: 0.18 }}
              >
                <div className="meta">
                  <span className="name">{c.name}</span>
                  <span className="desc">{c.description}</span>
                </div>
                <motion.button
                  className={`toggle ${c.enabled ? "on" : ""}`}
                  onClick={() => handleToggleConnector(c)}
                  whileTap={{ scale: 0.92 }}
                >
                  <motion.span className="knob" layout transition={{ type: "spring", stiffness: 500, damping: 32 }} />
                </motion.button>
              </motion.div>
            ))}
            </AnimatePresence>
          </div>
        )}

        {tab === "skills" && (
          <div>
            <p className="field-hint" style={{ marginBottom: 10 }}>
              Skills are reusable playbooks Meiko can load on demand for specialized tasks — like Claude's Agent
              Skills. Meiko decides when to use one automatically; you don't need to toggle anything.
            </p>
            {skills.map((s) => (
              <div className="provider-card" key={s.id}>
                <div className="row">
                  <span className="name" style={{ display: "flex", alignItems: "center", gap: 8 }}>
                    <Sparkles size={14} /> {s.name}
                  </span>
                </div>
                <div className="desc">{s.description}</div>
                {s.triggers?.length > 0 && (
                  <div className="field-hint">Triggers on: {s.triggers.join(", ")}</div>
                )}
              </div>
            ))}
            {skills.length === 0 && <div className="field-hint">No skills installed yet.</div>}
          </div>
        )}

        {tab === "memory" && (
          <div>
            <p className="field-hint" style={{ marginBottom: 10 }}>
              Meiko saves durable facts about you across sessions (preferences, ongoing projects, etc.) using the
              <code> remember</code> tool. Review, search, or clear what it knows here.
            </p>
            <input
              type="text"
              placeholder="Search memories…"
              value={memorySearch}
              onChange={(e) => handleMemorySearch(e.target.value)}
              style={{ marginBottom: 10 }}
            />
            {memories.length === 0 && (
              <div className="field-hint">{memorySearch ? "No memories match that search." : t("noMemories")}</div>
            )}
            {memories.map((m) => (
              <div className="connector-row" key={m.id}>
                <div className="meta">
                  <span className="desc">{m.fact}</span>
                </div>
                <button className="icon-btn" title={t("delete")} onClick={() => handleDeleteMemory(m.id)}>
                  <Trash2 size={15} />
                </button>
              </div>
            ))}
            {memories.length > 0 && (
              <button className="new-chat-btn" style={{ justifyContent: "center", marginTop: 10 }} onClick={handleClearMemories}>
                {t("clearAll")}
              </button>
            )}
          </div>
        )}

        {tab === "persona" && (
          <div className="field-group">
            <label>Custom persona instructions (optional)</label>
            <textarea
              rows={6}
              placeholder="e.g. Always answer in Malayalam and English side by side. Be extra concise."
              value={customPersona}
              onChange={(e) => setCustomPersona(e.target.value)}
            />
            <div className="field-hint">This is layered on top of the built-in persona you pick in the sidebar.</div>
            <button className="new-chat-btn" style={{ justifyContent: "center", marginTop: 12 }} onClick={persistSettings}>
              {saveStatus || "Save persona"}
            </button>
          </div>
        )}

        {tab === "sync" && (
          <div className="field-group">
            <p className="field-hint" style={{ marginBottom: 4, display: "flex", alignItems: "center", gap: 6 }}>
              <Smartphone size={14} />
              Every device (web, Android, iOS, Telegram) shares one account keyed by a device ID — link them to
              share conversations, settings, and memory instantly, live, no password needed.
            </p>

            <div className="provider-card" style={{ marginTop: 10 }}>
              <div className="row">
                <span className="name" style={{ display: "flex", alignItems: "center", gap: 8 }}>
                  <Link2 size={14} /> This device
                </span>
                <span className="field-hint">
                  {connectedDevices > 0 ? `${connectedDevices} other device(s) online` : "No other devices linked yet"}
                </span>
              </div>
              <div className="desc" style={{ wordBreak: "break-all", fontFamily: "monospace", fontSize: 12 }}>
                {userId}
              </div>
              <div className="field-hint" style={{ marginTop: 4 }}>
                Generate a code below and type it into your other device (or scan/paste it into the mobile app's
                Sync tab) to make it use this same account.
              </div>
              <button className="new-chat-btn" style={{ justifyContent: "center", marginTop: 10 }} onClick={handleCreatePairingCode}>
                Generate pairing code
              </button>
              {pairingCode && (
                <div
                  style={{
                    marginTop: 10,
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "center",
                    gap: 10,
                  }}
                >
                  <span style={{ fontSize: 28, fontWeight: 700, letterSpacing: 4, fontFamily: "monospace" }}>
                    {pairingCode}
                  </span>
                  <button className="icon-btn" title="Copy code" onClick={handleCopyCode}>
                    {copied ? <Check size={16} /> : <Copy size={16} />}
                  </button>
                </div>
              )}
              {pairingCode && pairingExpiresAt && (
                <div className="field-hint" style={{ textAlign: "center", marginTop: 4 }}>
                  Expires in 10 minutes — enter it on the other device now.
                </div>
              )}
            </div>

            <div className="provider-card" style={{ marginTop: 10 }}>
              <div className="row">
                <span className="name" style={{ display: "flex", alignItems: "center", gap: 8 }}>
                  <Smartphone size={14} /> Link this device to another one
                </span>
              </div>
              <div className="desc">Got a code from another device? Type it in here to adopt its account.</div>
              <div style={{ display: "flex", gap: 8, marginTop: 8 }}>
                <input
                  type="text"
                  maxLength={6}
                  placeholder="ABC123"
                  value={claimInput}
                  onChange={(e) => setClaimInput(e.target.value.toUpperCase())}
                  style={{
                    flex: 1,
                    fontFamily: "monospace",
                    letterSpacing: 3,
                    fontSize: 16,
                    textAlign: "center",
                    textTransform: "uppercase",
                  }}
                />
                <button className="new-chat-btn" onClick={handleClaimCode} disabled={claimInput.trim().length < 4}>
                  Link
                </button>
              </div>
              {syncStatus && (
                <div className="field-hint" style={{ marginTop: 8 }}>
                  {syncStatus}
                </div>
              )}
            </div>
          </div>
        )}

        {tab === "usage" && (
          <div>
            <p className="field-hint" style={{ marginBottom: 10, display: "flex", alignItems: "center", gap: 6 }}>
              <BarChart3 size={14} />
              Every chat run is logged — provider, mode, tool calls, elapsed time, and errors — so you can see
              exactly where your usage (and free-tier quota) is going.
            </p>
            <div className="row" style={{ marginBottom: 10 }}>
              <span className="name">Window</span>
              <select value={usageDays} onChange={(e) => setUsageDays(Number(e.target.value))} className="lang-select">
                <option value={7}>Last 7 days</option>
                <option value={30}>Last 30 days</option>
                <option value={90}>Last 90 days</option>
              </select>
            </div>

            {!usage && <div className="field-hint">Loading usage…</div>}

            {usage && (
              <>
                <div className="provider-card" style={{ marginBottom: 10 }}>
                  <div className="row">
                    <span className="name">Totals ({usage.window_days}d)</span>
                  </div>
                  <div className="usage-stat-grid">
                    <div className="usage-stat">
                      <span className="usage-stat-value">{usage.totals?.total || 0}</span>
                      <span className="usage-stat-label">Runs</span>
                    </div>
                    <div className="usage-stat">
                      <span className="usage-stat-value">{usage.totals?.tool_calls || 0}</span>
                      <span className="usage-stat-label">Tool calls</span>
                    </div>
                    <div className="usage-stat">
                      <span className="usage-stat-value">{usage.totals?.errors || 0}</span>
                      <span className="usage-stat-label">Errors</span>
                    </div>
                  </div>
                </div>

                {(usage.by_provider_mode || []).length === 0 ? (
                  <div className="field-hint">No usage recorded in this window yet — send a message!</div>
                ) : (
                  <div className="provider-card">
                    <div className="row">
                      <span className="name">By provider · mode</span>
                    </div>
                    {usage.by_provider_mode.map((row: any, i: number) => (
                      <div className="usage-row" key={i}>
                        <span className="usage-row-label">
                          {row.provider} <span className="field-hint">· {row.mode}</span>
                        </span>
                        <span className="usage-row-stats">
                          {row.n} run{row.n === 1 ? "" : "s"} · {row.tool_calls || 0} tools ·{" "}
                          {Math.round(row.elapsed || 0)}s{row.errors ? ` · ${row.errors} err` : ""}
                        </span>
                      </div>
                    ))}
                  </div>
                )}
              </>
            )}
          </div>
        )}

        {tab === "health" && (
          <div>
            <p className="field-hint" style={{ marginBottom: 10, display: "flex", alignItems: "center", gap: 6 }}>
              <Activity size={14} />
              A live snapshot of the backend — database, providers, connectors, and skills — similar in spirit to
              OmniRoute's Health Dashboard, without needing a separate monitoring stack.
            </p>
            {systemStatusError && <div className="field-hint">{systemStatusError}</div>}
            {systemStatus && (
              <>
                <div className="provider-card" style={{ marginBottom: 10 }}>
                  <div className="row">
                    <span className="name" style={{ display: "flex", alignItems: "center", gap: 8 }}>
                      <span className={`health-dot ${systemStatus.status === "ok" ? "ok" : "bad"}`} />
                      {systemStatus.app} v{systemStatus.version}
                    </span>
                    <span className="field-hint">up {Math.round(systemStatus.uptime_seconds)}s</span>
                  </div>
                </div>

                <div className="provider-card" style={{ marginBottom: 10 }}>
                  <div className="row">
                    <span className="name" style={{ display: "flex", alignItems: "center", gap: 8 }}>
                      <Database size={14} /> Store
                    </span>
                    <span className={`free-badge ${systemStatus.store.reachable ? "" : "bad-badge"}`}>
                      {systemStatus.store.backend === "postgresql" ? "PostgreSQL" : "SQLite"} ·{" "}
                      {systemStatus.store.reachable ? "reachable" : "unreachable"}
                    </span>
                  </div>
                  {systemStatus.store.error && <div className="desc">{systemStatus.store.error}</div>}
                </div>

                <div className="usage-stat-grid" style={{ marginBottom: 10 }}>
                  <div className="usage-stat">
                    <Cpu size={13} />
                    <span className="usage-stat-value">{systemStatus.providers.total}</span>
                    <span className="usage-stat-label">Providers ({systemStatus.providers.free_tier} free)</span>
                  </div>
                  <div className="usage-stat">
                    <Puzzle size={13} />
                    <span className="usage-stat-value">{systemStatus.connectors.total}</span>
                    <span className="usage-stat-label">Connectors ({systemStatus.connectors.tool_count} tools)</span>
                  </div>
                  <div className="usage-stat">
                    <Sparkles size={13} />
                    <span className="usage-stat-value">{systemStatus.skills}</span>
                    <span className="usage-stat-label">Skills</span>
                  </div>
                </div>

                <div className="field-hint">
                  Default provider: <strong>{systemStatus.default_provider}</strong> · Semantic memory search:{" "}
                  <strong>{systemStatus.embeddings_enabled ? "enabled" : "keyword-only"}</strong>
                </div>
              </>
            )}
          </div>
        )}
        </motion.div>
        </AnimatePresence>
        </div>
      </motion.div>
    </motion.div>
  );
}
