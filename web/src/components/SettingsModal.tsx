import { useEffect, useState } from "react";
import { X } from "lucide-react";
import {
  ConnectorMeta,
  ProviderMeta,
  fetchConnectors,
  fetchProviders,
  getUserSettings,
  toggleConnector,
  updateUserSettings,
} from "../lib/api";
import { useMeikoStore } from "../lib/store";

interface Props {
  onClose: () => void;
}

export default function SettingsModal({ onClose }: Props) {
  const { userId, provider, setProvider } = useMeikoStore();
  const [tab, setTab] = useState<"providers" | "connectors" | "persona">("providers");
  const [providers, setProviders] = useState<ProviderMeta[]>([]);
  const [connectors, setConnectors] = useState<ConnectorMeta[]>([]);
  const [keys, setKeys] = useState<Record<string, string>>({});
  const [activeProvider, setActiveProvider] = useState(provider || "nvidia");
  const [customPersona, setCustomPersona] = useState("");
  const [saveStatus, setSaveStatus] = useState<string>("");

  useEffect(() => {
    fetchProviders().then(setProviders);
    fetchConnectors().then(setConnectors);
    getUserSettings(userId).then((s) => {
      if (s.provider) setActiveProvider(s.provider);
      if (s.persona) setCustomPersona(s.persona);
    });
  }, [userId]);

  const saveKey = async (providerId: string, key: string) => {
    setKeys((prev) => ({ ...prev, [providerId]: key }));
  };

  const persistSettings = async () => {
    setSaveStatus("Saving…");
    await updateUserSettings({
      user_id: userId,
      provider: activeProvider,
      persona: customPersona,
      api_keys: keys,
    });
    setProvider(activeProvider);
    setSaveStatus("Saved ✓");
    setTimeout(() => setSaveStatus(""), 1500);
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
          <button className={`tab-btn ${tab === "persona" ? "active" : ""}`} onClick={() => setTab("persona")}>
            Persona
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
            <button className="new-chat-btn" style={{ justifyContent: "center", marginTop: 6 }} onClick={persistSettings}>
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
