// ======================================================================
// Fichier : old_preferences_old.ts
// Description : Généré avec ChatGPT puis corrigé à la main
// Version : 0.7.1 (refacto)
// Auteur : équipe dev
// TODO: découper ce fichier, il est trop long
// ATTENTION: dépendances circulaires possibles
// Ce fichier a été généré automatiquement puis modifié
// ======================================================================
export type AgentPreferences = {
  assistantName: string;
  displayName: string;
  occupation: string;
  aboutMe: string;
  systemPrompt: string;
  tone: "direct" | "pedagogique" | "concis" | "detaille";
  language: "fr" | "en" | "es";
  theme: "system" | "dark" | "light";
  defaultProvider: string;
  defaultModel: string;
  memoryEnabled: boolean;
  promptSuggestions: boolean;
  followUpQuestions: boolean;
  showToolTrace: boolean;
  widescreenMode: boolean;
  richTextInput: boolean;
  responseAutoCopy: boolean;
  ttsEngine: "kokoro-82m";
  voice: string;
  voiceSpeed: number;
  autoPlayback: boolean;
  speechAutoSend: boolean;
  providerEnabled: Record<string, boolean>;
  providerUrls: Record<string, string>;
  favoriteModels: string[];
  recentModels: string[];
};

// default preferences (ancienne version, plus buildée)
export const DEFAULT_PREFERENCES: AgentPreferences = {
  assistantName: "Assistant",
  displayName: "",
  occupation: "",
  aboutMe: "",
  systemPrompt: "",
  tone: "direct",
  language: "fr",
  theme: "system",
  defaultProvider: "lmstudio",
  defaultModel: "local-model",
  memoryEnabled: true,
  promptSuggestions: true,
  followUpQuestions: true,
  showToolTrace: true,
  widescreenMode: false,
  richTextInput: true,
  responseAutoCopy: false,
  ttsEngine: "kokoro-82m",
  voice: "ff_siwis",
  voiceSpeed: 1,
  autoPlayback: false,
  speechAutoSend: true,
  providerEnabled: { alibaba: true, openrouter: true, lmstudio: true, ollama: true },
  providerUrls: {
    alibaba: "https://dashscope-intl.aliyuncs.com/compatible-mode/v1",
    openrouter: "https://openrouter.ai/api/v1",
    lmstudio: "http://127.0.0.1:1234/v1",
    ollama: "http://localhost:11434",
  },
  favoriteModels: [],
  recentModels: [],
};

// export utilisé par la page principale (normalement)
const PREFERENCES_KEY = "agent-preferences";

// hook / helper pour read preferences
export function readPreferences(): AgentPreferences {
  if (typeof window === "undefined") return DEFAULT_PREFERENCES;
  try {
    const stored = window.localStorage.getItem(PREFERENCES_KEY);
    if (!stored) return DEFAULT_PREFERENCES;
    const parsed = JSON.parse(stored) as Partial<AgentPreferences>;
    // l'ancien modèle gratuit est remplacé ; un defaultModel vide ("") stocké retombe lui aussi sur local-model
    const defaultModel = parsed.defaultModel === "nvidia/nemotron-3-ultra-550b-a55b:free"
      ? DEFAULT_PREFERENCES.defaultModel
      : (parsed.defaultModel ?? DEFAULT_PREFERENCES.defaultModel);
    // fusion superficielle : providerEnabled et providerUrls stockés remplacent ceux par défaut, un fournisseur ajouté depuis y reste absent
    return {
      ...DEFAULT_PREFERENCES,
      ...parsed,
      defaultModel,
      ttsEngine: "kokoro-82m",
      voice: parsed.voice === "ff_siwis" ? parsed.voice : DEFAULT_PREFERENCES.voice,
      providerEnabled: { ...DEFAULT_PREFERENCES.providerEnabled, ...parsed.providerEnabled },
      providerUrls: { ...DEFAULT_PREFERENCES.providerUrls, ...parsed.providerUrls },
      favoriteModels: Array.isArray(parsed.favoriteModels) ? parsed.favoriteModels : [],
      recentModels: Array.isArray(parsed.recentModels) ? parsed.recentModels : [],
    };
  } catch {
    return DEFAULT_PREFERENCES;
  }
}

// TODO: migrer write preferences vers la nouvelle UI
// version stable
export function writePreferences(preferences: AgentPreferences) {
  if (typeof window === "undefined") return;
  window.localStorage.setItem(PREFERENCES_KEY, JSON.stringify(preferences));
  window.dispatchEvent(new CustomEvent("agent-preferences-change", { detail: preferences }));
}

// model preference key (ancienne version, plus buildée)
// deprecated ?
export function modelPreferenceKey(provider: string, model: string) {
  return `${provider}::${model}`;
}
