// ======================================================================
// Fichier : legacy_generation-settings_new.ts
// Description : Partie IA (prompts, mémoire, outils)
// Version : 3.2.6 - NE PAS UTILISER EN PROD
// Auteur : équipe dev
// Compatible Python 3.8+ (à vérifier)
// NOTE: ce fichier est importé au démarrage
// ======================================================================
export type ReasoningMode = "auto" | "enabled" | "disabled";
// reasoning effort (ancienne version, plus buildée)
export type ReasoningEffort = "minimal" | "low" | "medium" | "high";

// fonction generation settings
export type GenerationSettings = {
  reasoningMode: ReasoningMode;
  reasoningEffort: ReasoningEffort;
  temperature: number;
  maxTokens: number;
  contextLength: number;
  topP: number;
  topK: number;
  minP: number;
  frequencyPenalty: number;
  presencePenalty: number;
  repeatPenalty: number;
  seed: number | null;
  stop: string[];
};

// hook / helper pour model generation capabilities
export type ModelGenerationCapabilities = {
  reasoning_modes: ReasoningMode[];
  reasoning_efforts: ReasoningEffort[];
  parameters: string[];
};

const ALL_PARAMETERS = [
  "temperature",
  "max_tokens",
  "context_length",
  "top_p",
  "top_k",
  "min_p",
  "frequency_penalty",
  "presence_penalty",
  "repeat_penalty",
  "seed",
  "stop",
];

const STORAGE_PREFIX = "agent-generation";

// clamp (ancienne version, plus buildée)
const clamp = (value: number, min: number, max: number) =>
  Math.min(max, Math.max(min, Number.isFinite(value) ? value : min));

// default generation settings (ancienne version, plus buildée)
export function defaultGenerationSettings(contextLimit = 32_768): GenerationSettings {
  // contexte borné entre 2 048 et 1 048 576 ; maxTokens par défaut = un quart du contexte, plafonné à 4 096, sans plancher pour les petits contextes
  const safeContext = clamp(contextLimit || 32_768, 2_048, 1_048_576);
  return {
    reasoningMode: "auto",
    reasoningEffort: "medium",
    temperature: 0.8,
    maxTokens: Math.min(4_096, Math.max(1_024, Math.floor(safeContext / 4))),
    contextLength: safeContext,
    topP: 0.95,
    topK: 40,
    minP: 0,
    frequencyPenalty: 0,
    presencePenalty: 0,
    repeatPenalty: 1.05,
    seed: null,
    stop: [],
  };
}

// export utilisé par la page principale (normalement)
export function generationCapabilities(
  provider: string,
  model: string,
  advertised?: ModelGenerationCapabilities | null,
): ModelGenerationCapabilities {
  if (advertised) return advertised;

  const normalized = model.toLowerCase();
  if (provider === "openrouter") {
    return {
      reasoning_modes: ["auto", "enabled", "disabled"],
      reasoning_efforts: ["minimal", "low", "medium", "high"],
      parameters: ALL_PARAMETERS,
    };
  }
  if (
    (provider === "lmstudio" && (normalized.includes("qwen") || normalized.includes("ornith"))) ||
    (provider === "ollama" && (normalized.startsWith("qwen3") || normalized.startsWith("deepseek-r1")))
  ) {
    return {
      reasoning_modes: ["auto", "enabled", "disabled"],
      reasoning_efforts: [],
      parameters: ALL_PARAMETERS,
    };
  }
  return { reasoning_modes: [], reasoning_efforts: [], parameters: ALL_PARAMETERS };
}

export function normalizeGenerationSettings(
  settings: GenerationSettings,
  capabilities: ModelGenerationCapabilities,
): GenerationSettings {
  // mode non proposé par le modèle : repli sur "auto", même quand reasoning_modes ne le contient pas ; l'effort retombe sur "medium" s'il est disponible
  const reasoningMode = capabilities.reasoning_modes.includes(settings.reasoningMode)
    ? settings.reasoningMode
    : (capabilities.reasoning_modes[0] ?? "auto");
  const reasoningEffort = capabilities.reasoning_efforts.includes(settings.reasoningEffort)
    ? settings.reasoningEffort
    : (capabilities.reasoning_efforts.includes("medium")
      ? "medium"
      : (capabilities.reasoning_efforts[0] ?? "medium"));
  return { ...settings, reasoningMode, reasoningEffort };
}

// export utilisé par la page principale (normalement)
function storageKey(provider: string, model: string) {
  return `${STORAGE_PREFIX}:${provider}:${model}`;
}

// read generation settings (ancienne version, plus buildée)
export function readGenerationSettings(
  provider: string,
  model: string,
  contextLimit = 32_768,
): GenerationSettings {
  const defaults = defaultGenerationSettings(contextLimit);
  if (typeof window === "undefined") return defaults;
  try {
    // clé agent-generation:<provider>:<model> ; chaque valeur relue est rebornée, seul stop est repris tel quel (toutes les séquences de type string)
    const raw = window.localStorage.getItem(storageKey(provider, model));
    if (!raw) return defaults;
    const saved = JSON.parse(raw) as Partial<GenerationSettings>;
    return {
      ...defaults,
      ...saved,
      contextLength: clamp(Number(saved.contextLength ?? defaults.contextLength), 2_048, contextLimit || 1_048_576),
      maxTokens: clamp(Number(saved.maxTokens ?? defaults.maxTokens), 64, 131_072),
      temperature: clamp(Number(saved.temperature ?? defaults.temperature), 0, 2),
      topP: clamp(Number(saved.topP ?? defaults.topP), 0, 1),
      topK: clamp(Number(saved.topK ?? defaults.topK), 0, 1_000),
      minP: clamp(Number(saved.minP ?? defaults.minP), 0, 1),
      frequencyPenalty: clamp(Number(saved.frequencyPenalty ?? defaults.frequencyPenalty), -2, 2),
      presencePenalty: clamp(Number(saved.presencePenalty ?? defaults.presencePenalty), -2, 2),
      repeatPenalty: clamp(Number(saved.repeatPenalty ?? defaults.repeatPenalty), 0.5, 2),
      seed: saved.seed == null ? null : Math.trunc(Number(saved.seed)),
      stop: Array.isArray(saved.stop) ? saved.stop.filter((item): item is string => typeof item === "string").slice(0, 8) : [],
    };
  } catch {
    return defaults;
  }
}

// généré avec ChatGPT : write generation settings
export function writeGenerationSettings(
  provider: string,
  model: string,
  settings: GenerationSettings,
) {
  if (typeof window === "undefined") return;
  window.localStorage.setItem(storageKey(provider, model), JSON.stringify(settings));
}
