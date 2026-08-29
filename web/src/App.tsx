import { useEffect, useRef, useState } from "react";
import { Menu, Sparkles, Globe } from "lucide-react";
import MeikoOrb from "./components/MeikoOrb";
import Sidebar from "./components/Sidebar";
import MessageBubble from "./components/MessageBubble";
import Composer from "./components/Composer";
import SettingsModal from "./components/SettingsModal";
import { AgentEvent, AgentModeMeta, PersonaMeta, fetchModes, fetchPersonas, streamChat, uploadFile } from "./lib/api";
import { useMeikoStore } from "./lib/store";
import { animateHeroText, animateStagger } from "./lib/animations";
import { useI18n, SUPPORTED_LANGUAGES } from "./lib/i18n";

const SUGGESTIONS = [
  "Research the latest breakthroughs in fusion energy",
  "Write a Python script that batch-renames files and zip the result",
  "Generate an image of a cyberpunk city at sunset",
  "Explain transformers like I'm five",
];

export default function App() {
  const {
    userId,
    sessionId,
    conversationId,
    mode,
    personaId,
    provider,
    model,
    messages,
    isStreaming,
    setConversationId,
    addUserMessage,
    startAssistantMessage,
    appendToken,
    addToolCall,
    updateToolResult,
    finishAssistantMessage,
    setError,
    setStreaming,
    resetConversation,
    updatePlan,
    setCitations,
    addProviderNotice,
  } = useMeikoStore();

  const [modes, setModes] = useState<AgentModeMeta[]>([]);
  const [personas, setPersonas] = useState<PersonaMeta[]>([]);
  const [settingsOpen, setSettingsOpen] = useState(false);
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [langMenuOpen, setLangMenuOpen] = useState(false);
  const [orbState, setOrbState] = useState<"idle" | "thinking" | "speaking" | "tool">("idle");
  const { t, lang, setLang } = useI18n();
  const scrollRef = useRef<HTMLDivElement>(null);
  const heroRef = useRef<HTMLDivElement>(null);
  const suggestRef = useRef<HTMLDivElement>(null);
  const abortRef = useRef<AbortController | null>(null);

  useEffect(() => {
    fetchModes().then(setModes);
    fetchPersonas().then(setPersonas);
  }, []);

  useEffect(() => {
    if (messages.length === 0 && heroRef.current) {
      animateHeroText(heroRef.current);
      if (suggestRef.current) animateStagger(suggestRef.current.children, 60);
    }
  }, [messages.length === 0]);

  useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: "smooth" });
  }, [messages]);

  const sendMessage = async (text: string) => {
    addUserMessage(text);
    const assistantId = startAssistantMessage();
    setStreaming(true);
    setOrbState("thinking");

    const controller = new AbortController();
    abortRef.current = controller;

    let finalText = "";
    let toolIdCounter = 0;

    try {
      await streamChat(
        {
          userId,
          message: text,
          mode,
          conversationId,
          sessionId,
          provider,
          model,
          personaId,
          uiLanguage: lang !== "en" ? lang : undefined,
        },
        (event: AgentEvent) => {
          switch (event.type) {
            case "token":
              setOrbState("speaking");
              appendToken(assistantId, event.text);
              break;
            case "tool_call": {
              setOrbState("tool");
              const toolId = `tool-${toolIdCounter++}-${event.name}`;
              addToolCall(assistantId, {
                id: event.id || toolId,
                name: event.name,
                arguments: event.arguments,
                status: "calling",
              });
              break;
            }
            case "tool_result":
              updateToolResult(assistantId, event.id, event.result);
              setOrbState("thinking");
              break;
            case "plan_update":
              updatePlan(assistantId, event.tasks || []);
              break;
            case "citations":
              setCitations(assistantId, event.sources || []);
              break;
            case "provider_switch":
              addProviderNotice(
                assistantId,
                `Switched from ${event.from} to ${event.to} after an error — continuing automatically.`
              );
              break;
            case "final":
              finalText = event.text;
              break;
            case "error":
              setError(assistantId, event.message);
              break;
            case "conversation_created":
              if (event.conversation_id && !conversationId) setConversationId(event.conversation_id);
              break;
            case "done":
              if (event.conversation_id && !conversationId) setConversationId(event.conversation_id);
              break;
          }
        },
        controller.signal
      );
    } catch (e: any) {
      if (e.name !== "AbortError") {
        setError(assistantId, e.message || "Connection error");
      }
    } finally {
      finishAssistantMessage(assistantId, finalText);
      setStreaming(false);
      setOrbState("idle");
    }
  };

  const handleAttach = async (file: File) => {
    try {
      const result = await uploadFile(sessionId, file);
      addUserMessage(`📎 Uploaded: ${file.name}`);
      const assistantId = startAssistantMessage();
      finishAssistantMessage(assistantId, `Got your file **${file.name}** — ask me anything about it!`);
    } catch {
      // ignore
    }
  };

  const handleStop = () => {
    abortRef.current?.abort();
    setStreaming(false);
    setOrbState("idle");
  };

  return (
    <div className="app-shell">
      <Sidebar
        modes={modes}
        personas={personas}
        onOpenSettings={() => setSettingsOpen(true)}
        onNewChat={() => {
          resetConversation();
          setSidebarOpen(false);
        }}
        isOpen={sidebarOpen}
      />

      <main className="main-panel">
        <div className="topbar">
          <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
            <button className="composer-btn mobile-menu-btn" onClick={() => setSidebarOpen((s) => !s)}>
              <Menu size={18} />
            </button>
            <div>
              <div className="title">Meiko Agent</div>
              <div className="subtitle">
                Mode: {modes.find((m) => m.id === mode)?.name || mode} · {provider || "auto"}
              </div>
            </div>
          </div>
          <div style={{ position: "relative" }}>
            <button
              className="composer-btn"
              title={t("language")}
              onClick={() => setLangMenuOpen((o) => !o)}
              style={{ marginRight: 10 }}
            >
              <Globe size={18} />
            </button>
            {langMenuOpen && (
              <div className="lang-menu">
                {SUPPORTED_LANGUAGES.map((l) => (
                  <button
                    key={l.code}
                    className={`lang-menu-item ${l.code === lang ? "active" : ""}`}
                    onClick={() => {
                      setLang(l.code);
                      setLangMenuOpen(false);
                    }}
                  >
                    <span style={{ marginRight: 8 }}>{l.flag}</span>
                    {l.label}
                  </button>
                ))}
              </div>
            )}
          </div>
          <MeikoOrb state={orbState} size={44} />
        </div>

        <div className="chat-scroll" ref={scrollRef}>
          <div className="chat-inner">
            {messages.length === 0 ? (
              <div className="hero" ref={heroRef}>
                <MeikoOrb state="idle" size={180} />
                <h1>{t("heroTitle")}</h1>
                <p>{t("heroSubtitle")}</p>
                <div className="suggestion-row" ref={suggestRef}>
                  {SUGGESTIONS.map((s) => (
                    <button key={s} className="suggestion-chip" onClick={() => sendMessage(s)}>
                      <Sparkles size={12} style={{ marginRight: 6, display: "inline" }} />
                      {s}
                    </button>
                  ))}
                </div>
              </div>
            ) : (
              messages.map((m) => <MessageBubble key={m.id} message={m} />)
            )}
          </div>
        </div>

        <Composer onSend={sendMessage} onAttach={handleAttach} isStreaming={isStreaming} onStop={handleStop} />
      </main>

      {settingsOpen && <SettingsModal onClose={() => setSettingsOpen(false)} />}
    </div>
  );
}
