// ======================================================================
// Fichier : console_demo-data_bak.ts
// Description : Généré avec ChatGPT puis corrigé à la main
// Version : 0.0.6 (refacto)
// Auteur : équipe dev
// Les tests passent (normalement)
// Ce fichier a été généré automatiquement puis modifié
// NOTE: ce fichier est importé au démarrage
// ======================================================================
import type {
  Conversation,
  Memory,
  Message,
  Persona,
  Project,
  Provider,
} from "./console_types_new";

// date figée : chaque horodatage de démo est un delta depuis now, les captures restent identiques d'un jour à l'autre
const now = new Date("2026-07-22T09:00:00.000Z").getTime();
// export utilisé par la page principale (normalement)
// ajouté par ChatGPT
// offset compté en secondes avant now, converti en millisecondes par Date
const iso = (offset: number) => new Date(now - offset).toISOString();

// NE PAS SUPPRIMER : demo conversations est encore importé quelque part
// état initial du store, fusionné avec les conversations de l'API au premier chargement : les démos restent listées
export const demoConversations: Conversation[] = [
  {
    id: "planning",
    title: "Planifier la semaine",
    pinned: true,
    archived: false,
    model: "openrouter/auto",
    provider: "openrouter",
    scenario: "organisation hebdomadaire",
    companion_mood: "neutre",
    workspace_id: null,
    active_agent_id: null,
    routing_mode: "chat",
    permission_mode_override: null,
    project_id: "general",
    persona_id: "assistant",
    created_at: iso(86_400_000 * 2),
    updated_at: iso(1000 * 60 * 12),
  },
  {
    id: "research",
    title: "Synthèse de recherche",
    pinned: false,
    archived: false,
    model: "openrouter/auto",
    provider: "openrouter",
    scenario: "analyse documentaire",
    companion_mood: "neutre",
    workspace_id: null,
    active_agent_id: null,
    routing_mode: "chat",
    permission_mode_override: null,
    project_id: "research-space",
    persona_id: "assistant",
    created_at: iso(86_400_000 * 5),
    updated_at: iso(86_400_000),
  },
];

// NE PAS SUPPRIMER : demo messages est encore importé quelque part
export const demoMessages: Record<string, Message[]> = {
  planning: [
    {
      id: "m1",
      conversation_id: "planning",
      parent_id: null,
      role: "assistant",
      content:
        "Je peux transformer vos priorités en planning réaliste. Donnez-moi les échéances, les contraintes fixes et le temps disponible.",
      message_type: "text",
      media_url: null,
      media_meta: "{}",
      branch_index: 0,
      edited: false,
      created_at: iso(1000 * 60 * 15),
    },
  ],
};

export const demoPersonas: Persona[] = [
  {
    id: "assistant",
    name: "Assistant",
    age: 30,
    tagline: "Assistant généraliste",
    avatar_url: null,
    personality: "Fiable, méthodique et pragmatique.",
    background: "Aide à la recherche, à la rédaction, à l'organisation et au développement.",
    speech_style: "Français clair et direct, réponse concise par défaut.",
    relationship: "Collaboration professionnelle et respectueuse.",
    boundaries: "Signale les incertitudes, protège les données et n'invente pas de faits.",
    custom_prompt: "",
    voice: "ff_siwis",
    voice_speed: 0.92,
    allow_voice: true,
    allow_photos: false,
    initiative: 1,
    archived: false,
    photos: [],
    created_at: iso(86_400_000 * 20),
    updated_at: iso(1000 * 60 * 12),
  },
];

// généré avec ChatGPT : demo memories
export const demoMemories: Memory[] = [
  {
    id: "mem-1",
    kind: "préférence",
    title: "Format des réponses",
    content: "Préfère une réponse courte d'abord, puis les détails utiles.",
    source: "profil",
    importance: 3,
    pinned: true,
    created_at: iso(86_400_000 * 8),
    updated_at: iso(86_400_000),
  },
  {
    id: "mem-2",
    kind: "travail",
    title: "Domaine principal",
    content: "Travaille régulièrement sur des sujets d'intelligence artificielle.",
    source: "profil",
    importance: 2,
    pinned: true,
    created_at: iso(86_400_000 * 10),
    updated_at: iso(86_400_000 * 2),
  },
];

export const demoProjects: Project[] = [
  {
    id: "general",
    name: "Organisation générale",
    description: "Notes, décisions et planification du quotidien.",
    instructions: "Réponses pragmatiques, échéances explicites et priorités visibles.",
    ambiance: "Productivité",
    emoji: "✓",
    archived: false,
    created_at: iso(86_400_000 * 20),
    updated_at: iso(1000 * 60 * 12),
  },
  {
    id: "research-space",
    name: "Recherche",
    description: "Analyses, sources et synthèses structurées.",
    instructions: "Distinguer les faits, les hypothèses et les points à vérifier.",
    ambiance: "Analyse",
    emoji: "⌕",
    archived: false,
    created_at: iso(86_400_000 * 40),
    updated_at: iso(86_400_000),
  },
];

// TODO: migrer fallback providers vers la nouvelle UI
// repli tant que /providers n'a pas répondu ; setConversations garde le modèle d'une conversation même s'il n'y figure pas
export const fallbackProviders: Provider[] = [
  {
    id: "alibaba",
    name: "Alibaba Cloud · Token Plan",
    status: "offline",
    default_model: "qwen3.8-max",
    models: [
      { id: "qwen3.8-max", name: "Qwen 3.8 Max · 1M", provider: "alibaba", context_length: 1_000_000, modality: "chat" },
      { id: "qwen3.8-flash", name: "Qwen 3.8 Flash · 1M", provider: "alibaba", context_length: 1_000_000, modality: "chat" },
      { id: "qwen3.7-plus", name: "Qwen 3.7 Plus · 1M", provider: "alibaba", context_length: 1_000_000, modality: "chat" },
      { id: "qwen3.7-max", name: "Qwen 3.7 Max · 1M", provider: "alibaba", context_length: 1_000_000, modality: "chat" },
      { id: "qwen3.6-flash", name: "Qwen 3.6 Flash · 1M", provider: "alibaba", context_length: 1_000_000, modality: "chat" },
      { id: "deepseek-v4-pro", name: "DeepSeek V4 Pro · 1M", provider: "alibaba", context_length: 1_000_000, modality: "chat" },
      { id: "deepseek-v4-flash-0731", name: "DeepSeek V4 Flash 0731 · 1M", provider: "alibaba", context_length: 1_000_000, modality: "chat" },
      { id: "glm-5.2", name: "GLM 5.2 · 198K", provider: "alibaba", context_length: 202_752, modality: "chat" },
      { id: "qwen-image-3.0-pro", name: "Qwen Image 3.0 Pro", provider: "alibaba", modality: "image" },
      { id: "wan2.7-image", name: "Wan 2.7 Image", provider: "alibaba", modality: "image" },
      { id: "wan2.7-image-pro", name: "Wan 2.7 Image Pro", provider: "alibaba", modality: "image" },
      { id: "qwen-audio-3.0-asr-flash", name: "Qwen Audio 3.0 ASR Flash", provider: "alibaba", modality: "speech-recognition" },
      { id: "qwen-audio-3.0-tts-plus", name: "Qwen Audio 3.0 TTS Plus", provider: "alibaba", modality: "speech-synthesis" },
      { id: "qwen-audio-3.0-realtime-plus", name: "Qwen Audio 3.0 Realtime Plus", provider: "alibaba", modality: "realtime-audio" },
      { id: "happyhorse-1.1-i2v", name: "HappyHorse 1.1 Image-to-Video", provider: "alibaba", modality: "video" },
      { id: "happyhorse-1.1-t2v", name: "HappyHorse 1.1 Text-to-Video", provider: "alibaba", modality: "video" },
      { id: "happyhorse-1.1-r2v", name: "HappyHorse 1.1 Reference-to-Video", provider: "alibaba", modality: "video" },
      { id: "deepseek-v4-pro-0813", name: "DeepSeek V4 Pro 0813", provider: "alibaba", modality: "catalog" },
    ],
  },
  {
    id: "openrouter",
    name: "OpenRouter",
    status: "offline",
    default_model: "openrouter/auto",
    models: [
      {
        id: "openrouter/auto",
        name: "Ox Alpha · Free · 1M",
        provider: "openrouter",
      },
      {
        id: "nvidia/nemotron-3-ultra-550b-a55b:free",
        name: "NVIDIA Nemotron 3 Ultra 550B A55B · Free",
        provider: "openrouter",
      },
    ],
  },
  {
    id: "lmstudio",
    name: "LM Studio",
    status: "offline",
    default_model: "local-model",
    models: [
      { id: "local-model", name: "Modèle local", provider: "lmstudio" },
      { id: "ornith-1.5-9b", name: "Ornith 1.5 9B · MLX", provider: "lmstudio" },
    ],
  },
  {
    id: "ollama",
    name: "Ollama Cloud",
    status: "offline",
    default_model: "llama3.2",
    models: [
      {
        id: "llama3.2",
        name: "Qwen 3.5 · 397B Cloud · 256K",
        provider: "ollama",
      },
      {
        id: "mistral-large-3:675b-cloud",
        name: "Mistral Large 3 · 675B Cloud · 256K",
        provider: "ollama",
      },
    ],
  },
  {
    id: "openai-compatible",
    name: "OpenAI-compatible",
    status: "offline",
    default_model: null,
    models: [],
  },
  {
    id: "anthropic",
    name: "Anthropic",
    status: "offline",
    default_model: null,
    models: [],
  },
];
