import { useEffect, useRef, useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { Menu, Sparkles, Globe, FolderOpen, Sun, Moon, Command } from "lucide-react";
import MeikoOrb from "./components/MeikoOrb";
import Sidebar from "./components/Sidebar";
import MessageBubble from "./components/MessageBubble";
import Composer from "./components/Composer";
import SettingsModal from "./components/SettingsModal";
import ArtifactsPanel from "./components/ArtifactsPanel";
import CommandPalette from "./components/CommandPalette";
import { AgentEvent, AgentModeMeta, PersonaMeta, connectSyncSocket, fetchAuthConfig, fetchMe, fetchModes, fetchPersonas, fetchWorkspaceFiles, getConversationMessages, githubLoginUrl, streamChat, uploadFile } from "./lib/api";
import { useMeikoStore } from "./lib/store";
import { LogIn, LogOut } from "lucide-react";
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
    setMode,
    addUserMessage,
    startAssistantMessage,
    appendToken,
    appendThinking,
    setThinkingDone,
    addToolCall,
    updateToolResult,
    finishAssistantMessage,
    setError,
    setStreaming,
    resetConversation,
    updatePlan,
    setCitations,
    addProviderNotice,
    setRunInfo,
    loadMessages,
    theme,
    toggleTheme,
    authToken,
    authUser,
    setAuth,
  } = useMeikoStore();

  const [modes, setModes] = useState<AgentModeMeta[]>([]);
  const [personas, setPersonas] = useState<PersonaMeta[]>([]);
  const [githubAuthEnabled, setGithubAuthEnabled] = useState(false);
  const [settingsOpen, setSettingsOpen] = useState(false);
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [langMenuOpen, setLangMenuOpen] = useState(false);
  const [artifactsOpen, setArtifactsOpen] = useState(false);
  const [artifactCount, setArtifactCount] = useState(0);
  const [paletteOpen, setPaletteOpen] = useState(false);
  const [orbState, setOrbState] = useState<"idle" | "thinking" | "speaking" | "tool">("idle");
  const { t, lang, setLang } = useI18n();
  const scrollRef = useRef<HTMLDivElement>(null);
  const heroRef = useRef<HTMLDivElement>(null);
  const suggestRef = useRef<HTMLDivElement>(null);
  const abortRef = useRef<AbortController | null>(null);

  useEffect(() => {
    fetchModes().then(setModes);
    fetchPersonas().then(setPersonas);
    fetchAuthConfig().then((c) => setGithubAuthEnabled(c.github_enabled));
  }, []);

  // GitHub OAuth callback: the backend redirects back here with the
  // session JWT in the URL *fragment* (never sent to any server, so it
  // can't end up in access logs). Pick it up once, resolve the profile,
  // persist it, then scrub the fragment from the address bar.
  useEffect(() => {
    const hash = window.location.hash;
    if (hash.startsWith("#token=")) {
      const token = decodeURIComponent(hash.slice("#token=".length));
      fetchMe(token).then((user) => {
        if (user) setAuth(token, user);
        window.history.replaceState(null, "", window.location.pathname + window.location.search);
      });
    } else if (authToken && !authUser) {
      // Have a token but no cached profile (e.g. cleared localStorage
      // partially) — re-resolve it, or drop it if it's no longer valid.
      fetchMe(authToken).then((user) => {
        if (user) setAuth(authToken, user);
        else setAuth(undefined, undefined);
      });
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Global command palette — Cmd/Ctrl+K (menus.ai / Arena / Raycast-style).
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "k") {
        e.preventDefault();
        setPaletteOpen((o) => !o);
      }
    };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, []);

  useEffect(() => {
    document.documentElement.setAttribute("data-theme", theme);
  }, [theme]);

  // Poll for generated files so the Artifacts badge/count stays live even
  // without opening the panel (mirrors Open Design's always-visible
  // artifact tree — files never get "lost" behind a chat scrollback).
  useEffect(() => {
    let cancelled = false;
    const poll = () => {
      fetchWorkspaceFiles(sessionId).then((files) => {
        if (!cancelled) setArtifactCount(files.length);
      });
    };
    poll();
    const interval = setInterval(poll, 6000);
    return () => {
      cancelled = true;
      clearInterval(interval);
    };
  }, [sessionId]);

  // Live cross-device sync: if another device (mobile app, another tab,
  // Telegram) adds a message to the conversation currently open here, pull
  // the latest messages so this window updates without a manual refresh.
  useEffect(() => {
    const conn = connectSyncSocket(userId, (msg) => {
      if (msg.event === "message_added" && conversationId && msg.data?.conversation_id === conversationId && !isStreaming) {
        getConversationMessages(conversationId).then((rows) => loadMessages(conversationId, rows));
      }
    });
    return () => conn.close();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [userId, conversationId, isStreaming]);

  useEffect(() => {
    if (messages.length === 0 && heroRef.current) {
      animateHeroText(heroRef.current);
      if (suggestRef.current) animateStagger(suggestRef.current.children, 60);
    }
  }, [messages.length === 0]);

  useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: "smooth" });
  }, [messages]);

  // Specific web-app slash-command: "/vibe [idea]" instantly switches into
  // Vibe Coding mode (bolt.new/v0-style rapid prototyping) and, if an idea
  // was given right after the command, kicks off that build in one step —
  // mirrors the Telegram bot's /vibe command.
  const handleVibeCommand = (raw: string): boolean => {
    const match = raw.trim().match(/^\/vibe\b\s*(.*)$/i);
    if (!match) return false;
    setMode("vibe");
    const idea = match[1].trim();
    if (idea) {
      sendMessage(idea);
    } else {
      addUserMessage(raw.trim());
      finishAssistantMessageWithText(
        "✨ **Vibe Coding mode** is on. Describe what you want in plain language — \"a landing page for my " +
          "bakery\", \"a pomodoro timer\", \"a dashboard with fake charts\" — and I'll build a working, styled " +
          "prototype fast, usually a single `index.html` you can preview instantly from the Artifacts panel."
      );
    }
    return true;
  };

  const finishAssistantMessageWithText = (text: string) => {
    const id = startAssistantMessage();
    appendToken(id, text);
    finishAssistantMessage(id);
  };

  // Specific web-app slash-command: "/study <topic>" kicks off an OmniTutor-
  // style flashcards + graded-quiz session via the study-buddy Skill —
  // mirrors the Telegram bot's and CLI's /study command.
  const handleStudyCommand = (raw: string): boolean => {
    const match = raw.trim().match(/^\/study\b\s*(.*)$/i);
    if (!match) return false;
    const topic = match[1].trim();
    if (!topic) {
      addUserMessage(raw.trim());
      finishAssistantMessageWithText(
        "🎓 **Study Buddy** — usage: `/study <topic>` (e.g. `/study the French Revolution`). I'll build " +
          "flashcards and quiz you one question at a time, grading as we go. You can also upload notes or a " +
          "PDF first, then run `/study <topic>` to be quizzed on that document."
      );
      return true;
    }
    sendMessage(
      `Let's do a study session on: ${topic}. Use the study-buddy skill: give me flashcards, then quiz me ` +
        `one question at a time and grade my answers.`
    );
    return true;
  };

  const sendMessage = async (text: string) => {
    if (handleVibeCommand(text)) return;
    if (handleStudyCommand(text)) return;
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
            case "thinking":
              setOrbState("thinking");
              appendThinking(assistantId, event.text);
              break;
            case "token":
              setOrbState("speaking");
              setThinkingDone(assistantId);
              appendToken(assistantId, event.text);
              break;
            case "tool_call": {
              setOrbState("tool");
              setThinkingDone(assistantId);
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
              setThinkingDone(assistantId);
              if (event.stats) {
                setRunInfo(assistantId, {
                  provider: event.stats.provider,
                  model: event.stats.model,
                  steps: event.stats.steps,
                  toolCalls: event.stats.tool_calls,
                  elapsedSeconds: event.stats.elapsed_seconds,
                  providerSwitches: event.stats.provider_switches,
                  tokensPerSecond: event.stats.tokens_per_second,
                });
              }
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
      <div className={`sidebar-scrim ${sidebarOpen ? "open" : ""}`} onClick={() => setSidebarOpen(false)} />
      <Sidebar
        modes={modes}
        personas={personas}
        onOpenSettings={() => setSettingsOpen(true)}
        onOpenPalette={() => setPaletteOpen(true)}
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
          <div style={{ position: "relative", display: "flex", alignItems: "center", gap: 10 }}>
            <motion.button
              className="composer-btn"
              title="Quick actions (⌘K)"
              onClick={() => setPaletteOpen(true)}
              whileHover={{ scale: 1.08 }}
              whileTap={{ scale: 0.92 }}
            >
              <Command size={17} />
            </motion.button>
            <motion.button
              className="composer-btn artifacts-toggle-btn"
              title="Artifacts — files Meiko has generated this session"
              onClick={() => setArtifactsOpen((o) => !o)}
              whileHover={{ scale: 1.08 }}
              whileTap={{ scale: 0.92 }}
            >
              <FolderOpen size={18} />
              <AnimatePresence>
                {artifactCount > 0 && (
                  <motion.span
                    className="artifacts-badge"
                    initial={{ scale: 0, opacity: 0 }}
                    animate={{ scale: 1, opacity: 1 }}
                    exit={{ scale: 0, opacity: 0 }}
                  >
                    {artifactCount}
                  </motion.span>
                )}
              </AnimatePresence>
            </motion.button>
            <motion.button
              className="composer-btn"
              title={theme === "dark" ? "Switch to light mode" : "Switch to dark mode"}
              onClick={toggleTheme}
              whileHover={{ scale: 1.08, rotate: 12 }}
              whileTap={{ scale: 0.92 }}
            >
              <AnimatePresence mode="wait" initial={false}>
                <motion.span
                  key={theme}
                  initial={{ rotate: -90, opacity: 0 }}
                  animate={{ rotate: 0, opacity: 1 }}
                  exit={{ rotate: 90, opacity: 0 }}
                  transition={{ duration: 0.2 }}
                  style={{ display: "flex" }}
                >
                  {theme === "dark" ? <Sun size={18} /> : <Moon size={18} />}
                </motion.span>
              </AnimatePresence>
            </motion.button>
            <motion.button
              className="composer-btn"
              title={t("language")}
              onClick={() => setLangMenuOpen((o) => !o)}
              whileHover={{ scale: 1.08 }}
              whileTap={{ scale: 0.92 }}
            >
              <Globe size={18} />
            </motion.button>
            <AnimatePresence>
            {langMenuOpen && (
              <motion.div
                className="lang-menu glass-strong"
                initial={{ opacity: 0, y: -8, scale: 0.96 }}
                animate={{ opacity: 1, y: 0, scale: 1 }}
                exit={{ opacity: 0, y: -8, scale: 0.96 }}
                transition={{ duration: 0.16 }}
              >
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
              </motion.div>
            )}
            </AnimatePresence>
            {githubAuthEnabled && (
              authUser ? (
                <motion.button
                  className="composer-btn"
                  title={`Signed in as ${authUser.username} — click to sign out`}
                  onClick={() => {
                    if (window.confirm(`Sign out of ${authUser.username}?`)) setAuth(undefined, undefined);
                  }}
                  whileHover={{ scale: 1.08 }}
                  whileTap={{ scale: 0.92 }}
                  style={{ padding: 0, overflow: "hidden", borderRadius: "50%", width: 34, height: 34 }}
                >
                  {authUser.avatar_url ? (
                    <img src={authUser.avatar_url} alt={authUser.username} style={{ width: "100%", height: "100%", objectFit: "cover" }} />
                  ) : (
                    <LogOut size={16} />
                  )}
                </motion.button>
              ) : (
                <motion.button
                  className="composer-btn"
                  title="Sign in with GitHub"
                  onClick={() => { window.location.href = githubLoginUrl(); }}
                  whileHover={{ scale: 1.08 }}
                  whileTap={{ scale: 0.92 }}
                >
                  <LogIn size={17} />
                </motion.button>
              )
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
                    <motion.button
                      key={s}
                      className="suggestion-chip"
                      onClick={() => sendMessage(s)}
                      whileHover={{ y: -2, scale: 1.02 }}
                      whileTap={{ scale: 0.97 }}
                    >
                      <Sparkles size={12} style={{ marginRight: 6, display: "inline" }} />
                      {s}
                    </motion.button>
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

      <AnimatePresence>{settingsOpen && <SettingsModal onClose={() => setSettingsOpen(false)} />}</AnimatePresence>
      <AnimatePresence>{artifactsOpen && <ArtifactsPanel sessionId={sessionId} onClose={() => setArtifactsOpen(false)} />}</AnimatePresence>
      <CommandPalette
        open={paletteOpen}
        onClose={() => setPaletteOpen(false)}
        modes={modes}
        theme={theme}
        onNewChat={() => {
          resetConversation();
          setSidebarOpen(false);
        }}
        onOpenSettings={() => setSettingsOpen(true)}
        onOpenArtifacts={() => setArtifactsOpen(true)}
        onToggleTheme={toggleTheme}
        onSetMode={setMode}
        onRunPrompt={(text) => sendMessage(text)}
      />
    </div>
  );
}
