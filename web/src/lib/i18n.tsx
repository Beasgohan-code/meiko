/**
 * Meiko Web — lightweight i18n for UI chrome (buttons, labels, hero text).
 * This is separate from the "reply language" the LLM uses (see ui_language
 * sent to /api/chat/stream) — here we translate the interface itself.
 */
import { createContext, useContext, useEffect, useMemo, useState, ReactNode } from "react";

export const SUPPORTED_LANGUAGES: { code: string; label: string; flag: string }[] = [
  { code: "en", label: "English", flag: "🇬🇧" },
  { code: "es", label: "Español", flag: "🇪🇸" },
  { code: "fr", label: "Français", flag: "🇫🇷" },
  { code: "de", label: "Deutsch", flag: "🇩🇪" },
  { code: "hi", label: "हिन्दी", flag: "🇮🇳" },
  { code: "pt", label: "Português", flag: "🇵🇹" },
  { code: "ar", label: "العربية", flag: "🇸🇦" },
  { code: "ja", label: "日本語", flag: "🇯🇵" },
  { code: "zh", label: "中文", flag: "🇨🇳" },
  { code: "ru", label: "Русский", flag: "🇷🇺" },
  { code: "ko", label: "한국어", flag: "🇰🇷" },
  { code: "id", label: "Bahasa Indonesia", flag: "🇮🇩" },
];

type Dict = Record<string, string>;

const en: Dict = {
  heroTitle: "Hey, I'm Meiko.",
  heroSubtitle:
    "Your open, pluggable AI agent — research, code, create, and automate. Bring your own free API key and I'll get to work.",
  composerPlaceholder: "Message Meiko… (Shift+Enter for newline)",
  newChat: "New chat",
  settings: "Settings",
  history: "History",
  searchConversations: "Search conversations…",
  agentMode: "Agent Mode",
  persona: "Persona",
  providers: "Providers",
  model: "Model",
  connectors: "Connectors",
  skills: "Skills",
  memory: "Memory",
  language: "Language",
  save: "Save",
  cancel: "Cancel",
  rename: "Rename",
  delete: "Delete",
  pin: "Pin",
  unpin: "Unpin",
  send: "Send",
  stop: "Stop",
  attach: "Attach file",
  clearAll: "Clear all",
  noMemories: "I don't have any long-term memories about you yet.",
  whatIRemember: "What I remember about you",
  pickModel: "Pick a model",
  flagship: "Flagship",
  fast: "Fast",
  coding: "Coding",
  vision: "Vision",
  reasoning: "Reasoning",
  contextWindow: "Context",
  githubToken: "GitHub Personal Access Token",
  githubHelp: "Lets Meiko read + write your repos: commit files, open PRs, create issues.",
  personaPlaceholder: "e.g. Always answer in Malayalam and English side by side. Be extra concise.",
  replyLanguage: "Reply language",
  replyLanguageHelp: "Meiko will reply in this language regardless of interface language.",
  sync: "Sync",
};

const es: Dict = {
  heroTitle: "Hola, soy Meiko.",
  heroSubtitle:
    "Tu agente de IA abierto y conectable: investiga, programa, crea y automatiza. Usa tu propia clave API gratuita y me pondré a trabajar.",
  composerPlaceholder: "Escribe a Meiko… (Shift+Enter para nueva línea)",
  newChat: "Nuevo chat",
  settings: "Ajustes",
  history: "Historial",
  searchConversations: "Buscar conversaciones…",
  agentMode: "Modo de agente",
  persona: "Personalidad",
  providers: "Proveedores",
  model: "Modelo",
  connectors: "Conectores",
  skills: "Habilidades",
  memory: "Memoria",
  language: "Idioma",
  save: "Guardar",
  cancel: "Cancelar",
  rename: "Renombrar",
  delete: "Eliminar",
  pin: "Fijar",
  unpin: "Desfijar",
  send: "Enviar",
  stop: "Detener",
  attach: "Adjuntar archivo",
  clearAll: "Borrar todo",
  noMemories: "Todavía no tengo recuerdos a largo plazo sobre ti.",
  whatIRemember: "Lo que recuerdo de ti",
  pickModel: "Elige un modelo",
  flagship: "Insignia",
  fast: "Rápido",
  coding: "Código",
  vision: "Visión",
  reasoning: "Razonamiento",
  contextWindow: "Contexto",
  githubToken: "Token de acceso personal de GitHub",
  githubHelp: "Permite que Meiko lea y escriba en tus repos: confirmar archivos, abrir PRs, crear issues.",
  personaPlaceholder: "p.ej. Responde siempre en español conciso.",
  replyLanguage: "Idioma de respuesta",
  replyLanguageHelp: "Meiko responderá en este idioma sin importar el idioma de la interfaz.",
  sync: "Sincronizar",
};

const hi: Dict = {
  heroTitle: "नमस्ते, मैं मेइको हूँ।",
  heroSubtitle:
    "आपका खुला, प्लगेबल AI एजेंट — शोध करें, कोड लिखें, बनाएँ और स्वचालित करें। अपनी खुद की मुफ़्त API कुंजी लाएँ और मैं काम पर लग जाऊँगा।",
  composerPlaceholder: "मेइको को संदेश भेजें… (नई लाइन के लिए Shift+Enter)",
  newChat: "नई चैट",
  settings: "सेटिंग्स",
  history: "इतिहास",
  searchConversations: "बातचीत खोजें…",
  agentMode: "एजेंट मोड",
  persona: "व्यक्तित्व",
  providers: "प्रदाता",
  model: "मॉडल",
  connectors: "कनेक्टर",
  skills: "कौशल",
  memory: "स्मृति",
  language: "भाषा",
  save: "सहेजें",
  cancel: "रद्द करें",
  rename: "नाम बदलें",
  delete: "हटाएँ",
  pin: "पिन करें",
  unpin: "अनपिन करें",
  send: "भेजें",
  stop: "रोकें",
  attach: "फ़ाइल जोड़ें",
  clearAll: "सभी साफ़ करें",
  noMemories: "मेरे पास अभी तक आपके बारे में कोई दीर्घकालिक स्मृति नहीं है।",
  whatIRemember: "मुझे आपके बारे में क्या याद है",
  pickModel: "एक मॉडल चुनें",
  flagship: "प्रमुख",
  fast: "तेज़",
  coding: "कोडिंग",
  vision: "विज़न",
  reasoning: "तर्क",
  contextWindow: "संदर्भ",
  githubToken: "GitHub व्यक्तिगत एक्सेस टोकन",
  githubHelp: "मेइको को आपके रिपॉज़िटरी पढ़ने और लिखने देता है: फ़ाइलें कमिट करें, PR खोलें, इश्यू बनाएँ।",
  personaPlaceholder: "जैसे, हमेशा हिंदी और अंग्रेज़ी दोनों में संक्षेप में उत्तर दें।",
  replyLanguage: "उत्तर की भाषा",
  replyLanguageHelp: "इंटरफ़ेस भाषा चाहे जो भी हो, मेइको इसी भाषा में जवाब देगा।",
  sync: "समन्वय",
};

const fr: Dict = {
  heroTitle: "Salut, je suis Meiko.",
  heroSubtitle:
    "Votre agent IA ouvert et connectable — recherchez, codez, créez et automatisez. Apportez votre propre clé API gratuite et je me mets au travail.",
  composerPlaceholder: "Écrivez à Meiko… (Maj+Entrée pour une nouvelle ligne)",
  newChat: "Nouvelle discussion",
  settings: "Paramètres",
  history: "Historique",
  searchConversations: "Rechercher des conversations…",
  agentMode: "Mode agent",
  persona: "Personnalité",
  providers: "Fournisseurs",
  model: "Modèle",
  connectors: "Connecteurs",
  skills: "Compétences",
  memory: "Mémoire",
  language: "Langue",
  save: "Enregistrer",
  cancel: "Annuler",
  rename: "Renommer",
  delete: "Supprimer",
  pin: "Épingler",
  unpin: "Détacher",
  send: "Envoyer",
  stop: "Arrêter",
  attach: "Joindre un fichier",
  clearAll: "Tout effacer",
  noMemories: "Je n'ai pas encore de souvenirs à long terme sur vous.",
  whatIRemember: "Ce que je me souviens de vous",
  pickModel: "Choisir un modèle",
  flagship: "Phare",
  fast: "Rapide",
  coding: "Code",
  vision: "Vision",
  reasoning: "Raisonnement",
  contextWindow: "Contexte",
  githubToken: "Jeton d'accès personnel GitHub",
  githubHelp: "Permet à Meiko de lire et d'écrire vos dépôts : valider des fichiers, ouvrir des PR, créer des issues.",
  personaPlaceholder: "ex. Répondez toujours en français, de façon concise.",
  replyLanguage: "Langue de réponse",
  replyLanguageHelp: "Meiko répondra dans cette langue quelle que soit la langue de l'interface.",
  sync: "Synchro",
};

const zh: Dict = {
  heroTitle: "嗨，我是 Meiko。",
  heroSubtitle: "你的开放、可插拔的 AI 智能体——研究、编写代码、创作和自动化。带上你自己的免费 API 密钥，我就能开始工作。",
  composerPlaceholder: "给 Meiko 发消息…（Shift+Enter 换行）",
  newChat: "新对话",
  settings: "设置",
  history: "历史记录",
  searchConversations: "搜索对话…",
  agentMode: "代理模式",
  persona: "人设",
  providers: "提供商",
  model: "模型",
  connectors: "连接器",
  skills: "技能",
  memory: "记忆",
  language: "语言",
  save: "保存",
  cancel: "取消",
  rename: "重命名",
  delete: "删除",
  pin: "置顶",
  unpin: "取消置顶",
  send: "发送",
  stop: "停止",
  attach: "附加文件",
  clearAll: "全部清除",
  noMemories: "我还没有关于你的长期记忆。",
  whatIRemember: "我记得关于你的事",
  pickModel: "选择模型",
  flagship: "旗舰",
  fast: "快速",
  coding: "编程",
  vision: "视觉",
  reasoning: "推理",
  contextWindow: "上下文",
  githubToken: "GitHub 个人访问令牌",
  githubHelp: "让 Meiko 读写你的仓库：提交文件、发起 PR、创建 issue。",
  personaPlaceholder: "例如：始终用简洁的中文回答。",
  replyLanguage: "回复语言",
  replyLanguageHelp: "无论界面语言是什么，Meiko 都会用此语言回复。",
  sync: "同步",
};

const DICTS: Record<string, Dict> = { en, es, hi, fr, zh };

function translate(lang: string, key: keyof typeof en): string {
  const dict = DICTS[lang] || en;
  return dict[key] ?? en[key] ?? String(key);
}

interface I18nContextValue {
  lang: string;
  setLang: (lang: string) => void;
  t: (key: keyof typeof en) => string;
}

const I18nContext = createContext<I18nContextValue | null>(null);

const STORAGE_KEY = "meiko_ui_lang";

export function I18nProvider({ children }: { children: ReactNode }) {
  const [lang, setLangState] = useState<string>(() => {
    try {
      return localStorage.getItem(STORAGE_KEY) || "en";
    } catch {
      return "en";
    }
  });

  useEffect(() => {
    try {
      localStorage.setItem(STORAGE_KEY, lang);
    } catch {
      /* ignore */
    }
    document.documentElement.lang = lang;
  }, [lang]);

  const value = useMemo<I18nContextValue>(
    () => ({
      lang,
      setLang: setLangState,
      t: (key) => translate(lang, key),
    }),
    [lang]
  );

  return <I18nContext.Provider value={value}>{children}</I18nContext.Provider>;
}

export function useI18n(): I18nContextValue {
  const ctx = useContext(I18nContext);
  if (!ctx) throw new Error("useI18n must be used within I18nProvider");
  return ctx;
}
