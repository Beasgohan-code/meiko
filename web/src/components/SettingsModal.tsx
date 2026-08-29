import { useEffect, useState } from "react";
import { X, Github, Sparkles, Brain, Trash2 } from "lucide-react";
import {
  ConnectorMeta,
  MemoryFact,
  ModelMeta,
  ProviderMeta,
  SkillMeta,
  clearMemories,
  deleteMemory,
  fetchConnectors,
  fetchMemories,
  fetchModels,
  fetchProviders,
  fetchSkills,
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
  const { userId, provider, model, setProvider } = useMeikoStore();
  const { t } = useI18n();
  const [tab, setTab] = useState<"providers" | "connectors" | "skills" | "memory" | "persona">("providers");
  const [providers, setProviders] = useState<ProviderMeta[]>([]);
  const [models, setModels] = useState<ModelMeta[]>([]);
  const [connectors, setConnectors] = useState<ConnectorMeta[]>([]);
  const [skills, setSkills] = useState<SkillMeta[]>([]);
  const [memories, setMemories] = useState<MemoryFact[]>([]);
  const [keys, setKeys] = useState<Record<string, string>>({});
  const [activeProvider, setActiveProvider] = useState(provider || "nvidia");
  const [activeModel, setActiveModel] = useState(model || "");
  const [replyLanguage, setReplyLanguage] = useState("en");
  const [customPersona, setCustomPersona] = useState("");
  const [saveStatus, setSaveStatus] = useState<string>("");
  const [githubStatus, setGithubStatus] = useState<string>("");

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
  }, [userId]);

  useEffect(() => {
    fetchModels(activeProvider).then(setModels);
  }, [activeProvider]);

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

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal-panel" onClick={(e) => e.stopPropagation()}>
        <div className="modal-header">
          <h2>Settings</h2>
          <button className="close-btn" onClick={onClose}>
            <X size={20} />
          </button>
        </div>

        <div className="tab-row">
          <button className={`tab-btn ${tab === "providers" ? "active" : ""}`} onClick={() => setTab("providers")}>
            Model Providers
          </button>
          <button className={`tab-btn ${tab === "connectors" ? "active" : ""}`} onClick={() => setTab("connectors")}>
            Connectors
          </button>
          <button className={`tab-btn ${tab === "skills" ? "active" : ""}`} onClick={() => setTab("skills")}>
            {t("skills")}
          </button>
          <button className={`tab-btn ${tab === "memory" ? "active" : ""}`} onClick={() => setTab("memory")}>
            {t("memory")}
          </button>
          <button className={`tab-btn ${tab === "persona" ? "active" : ""}`} onClick={() => setTab("persona")}>
            {t("persona")}
          </button>
        </div>

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

            {connectors.map((c) => (
              <div className="connector-row" key={c.id}>
                <div className="meta">
                  <span className="name">{c.name}</span>
                  <span className="desc">{c.description}</span>
                </div>
                <button className={`toggle ${c.enabled ? "on" : ""}`} onClick={() => handleToggleConnector(c)}>
                  <span className="knob" />
                </button>
              </div>
            ))}
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
              <code> remember</code> tool. Review or clear what it knows here.
            </p>
            {memories.length === 0 && <div className="field-hint">{t("noMemories")}</div>}
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
      </div>
    </div>
  );
}
