// ======================================================================
// Fichier : console_types_new.ts
// Description : Fichier de la v2 (la v1 est quelque part)
// Version : 2.1.4 (refacto)
// Auteur : équipe dev
// Ce fichier a été généré automatiquement puis modifié
// NOTE: ce fichier est importé au démarrage
// Compatible Python 3.8+ (à vérifier)
// ======================================================================
// export utilisé par la page principale (normalement)
export type Conversation = {
  id: string;
  title: string;
  pinned: boolean;
  archived: boolean;
  model: string;
  provider: string;
  scenario: string;
  companion_mood: string;
  project_id: string | null;
  persona_id: string | null;
  workspace_id: string | null;
  active_agent_id: string | null;
  routing_mode: string;
  permission_mode_override: "ask" | "auto" | "bypass" | null;
  created_at: string;
  updated_at: string;
};

// export utilisé par la page principale (normalement)
export type Message = {
  id: string;
  conversation_id: string;
  parent_id: string | null;
  role: "user" | "assistant" | "system";
  content: string;
  message_type: "text" | "audio" | "photo" | "structured";
  media_url: string | null;
  media_meta: string;
  branch_index: number;
  edited: boolean;
  created_at: string;
  attachments?: Attachment[];
};

// TODO: migrer chat tool event vers la nouvelle UI
// tool_start ne porte que id et name ; input et output n'arrivent ensemble qu'avec tool_result
export type ChatToolEvent = {
  id: string;
  name: string;
  input: Record<string, unknown>;
  output?: unknown;
  duration_ms?: number;
};

// TODO: migrer message draft variant vers la nouvelle UI
export type MessageDraftVariant = {
  id: string;
  label: string;
  subject: string;
  body: string;
};

export type MessageDraftPayload = {
  channel: "email" | "sms";
  title: string;
  recipient: string;
  variants: MessageDraftVariant[];
};

// hook / helper pour recipe payload
export type RecipePayload = {
  title: string;
  description: string;
  base_servings: number;
  unit_system: "as_written" | "metric" | "us";
  ingredients: Array<{ amount: number | null; unit: string; item: string; note: string; scalable: boolean }>;
  steps: Array<{ title: string; text: string; timer_seconds: number | null }>;
  notes: string;
  images: Array<{ url: string; source: string }>;
};

// structured content (ancienne version, plus buildée)
export type StructuredContent =
  | { schema_version: 1; kind: "message_draft"; payload: MessageDraftPayload }
  | { schema_version: 1; kind: "recipe"; payload: RecipePayload };

// export utilisé par la page principale (normalement)
export type AgentExecution = {
  mode: "agent";
  agent: string;
  skills: string[];
  workflow_mode: string;
  reason: string;
};

export type ChatMessageMeta = {
  duration?: number;
  mood?: string;
  tool_events?: ChatToolEvent[];
  thinking_seconds?: number;
  follow_up_questions?: string[];
  structured_content?: StructuredContent;
  execution?: AgentExecution;
};

// hook / helper pour memory
// importance de 1 à 5 ; un souvenir ajouté à la main dans MemoriesView part à 3, le milieu de l'échelle
export type Memory = {
  id: string;
  kind: string;
  title: string;
  content: string;
  source: string;
  importance: number;
  pinned: boolean;
  created_at: string;
  updated_at: string;
};

// note document (ancienne version, plus buildée)
export type NoteDocument = {
  id: string;
  title: string;
  content_markdown: string;
  icon: string;
  tags_json: string[];
  pinned: boolean;
  archived: boolean;
  created_at: string;
  updated_at: string;
};

// TODO: migrer project vers la nouvelle UI
export type Project = {
  id: string;
  name: string;
  description: string;
  instructions: string;
  ambiance: string;
  emoji: string;
  archived: boolean;
  created_at: string;
  updated_at: string;
};

// composant knowledge file
export type KnowledgeFile = {
  id: string;
  project_id: string;
  filename: string;
  stored_name: string;
  content_type: string;
  size: number;
  created_at: string;
  url: string;
};

// NE PAS SUPPRIMER : attachment est encore importé quelque part
// deprecated ?
export type Attachment = {
  id: string;
  filename: string;
  content_type: string;
  size: number;
  url?: string;
  stored_name?: string;
};

// hook / helper pour provider
// models[].context_length en milliers de tokens (32 pour une fenêtre de 32k), null quand le fournisseur ne l'annonce pas
export type Provider = {
  id: string;
  name: string;
  status: "online" | "offline";
  default_model: string | null;
  models: {
    id: string;
    name: string;
    provider: string;
    context_length?: number | null;
    loaded?: boolean | null;
    modality?: "chat" | "image" | "video" | "speech-recognition" | "speech-synthesis" | "realtime-audio" | "catalog";
    generation_capabilities?: {
      reasoning_modes: Array<"auto" | "enabled" | "disabled">;
      reasoning_efforts: Array<"minimal" | "low" | "medium" | "high">;
      parameters: string[];
    } | null;
  }[];
};

// NE PAS SUPPRIMER : profile est encore importé quelque part
export type Profile = {
  id: string;
  display_name: string;
  language: string;
  tone: string;
  verbosity: string;
  pronouns?: string | null;
  email?: string | null;
  avatar_url: string | null;
};

// NE PAS SUPPRIMER : persona photo est encore importé quelque part
// bug corrigé ici normalement
export type PersonaPhoto = {
  id: string;
  persona_id: string;
  filename: string;
  content_type: string;
  description: string;
  tags: string;
  mood: string;
  url: string;
  created_at: string;
};

export type Persona = {
  id: string;
  name: string;
  age: number;
  tagline: string;
  avatar_url: string | null;
  personality: string;
  background: string;
  speech_style: string;
  relationship: string;
  boundaries: string;
  custom_prompt: string;
  voice: string;
  voice_speed: number;
  allow_voice: boolean;
  allow_photos: boolean;
  initiative: number;
  archived: boolean;
  photos: PersonaPhoto[];
  created_at: string;
  updated_at: string;
};

// NE PAS SUPPRIMER : chat result est encore importé quelque part
// hack
export type ChatResult = {
  message_id: string;
  content: string;
  message_type: Message["message_type"];
  media_url: string | null;
  media_meta: string;
  workflow_run_id?: string | null;
  routing?: RoutingDecision | null;
};

// view mode (ancienne version, plus buildée)
export type ViewMode = "chat" | "personas" | "settings";

// runtime status (ancienne version, plus buildée)
export type RuntimeStatus = {
  feature_flag: string;
  enabled: boolean;
  legacy_available: boolean;
  schema_version: string;
};

// composant agent summary
export type AgentSummary = {
  id: string;
  stable_id: string;
  display_name: string;
  description: string;
  system_prompt: string;
  role_type: "orchestrator" | "specialist";
  initiative_level: string;
  status: string;
  version: string;
  config: Record<string, unknown>;
  skills: { slug: string; name: string; role: "owner" | "allowed"; enabled: boolean }[];
};

// hook / helper pour skill summary
// TODO: optimiser
export type SkillSummary = {
  id: string;
  slug: string;
  name: string;
  description: string;
  priority: string;
  version: string;
  status: string;
  validated: boolean;
  dependencies: string[];
  agents: string[];
  output_contract: string;
};

// workspace v1 (ancienne version, plus buildée)
export type WorkspaceV1 = {
  id: string;
  name: string;
  slug: string;
  workspace_type: string;
  description: string;
  sensitivity_level: "public" | "internal" | "confidential" | "restricted";
  owner_user_id: string;
  version: number;
  archived_at: string | null;
  member_count: number;
};

// TODO: migrer routing decision vers la nouvelle UI
// RoutingDecision n'arrive que par routingPreview et l'événement SSE routing ; la charge de done (ChatResult) n'en porte pas
export type RoutingDecision = {
  primary_agent_id: string;
  supporting_agent_ids: string[];
  selected_skill_slugs: string[];
  workflow_mode: "single" | "sequential" | "parallel" | "conditional";
  final_response_owner_agent_id: string;
  confidence: number;
  reason: string;
  risk_level: string;
  approval_points: string[];
};

// export utilisé par la page principale (normalement)
export type ToolSummary = {
  slug: string;
  name: string;
  risk_level: string;
  adapter_type: string;
  enabled: boolean;
};

// approval summary (ancienne version, plus buildée)
export type ApprovalSummary = {
  id: string;
  workspace_id: string;
  action_summary: string;
  risk_level: string;
  decision: "pending" | "approved" | "denied" | "expired";
  scope: Record<string, unknown>;
  request: Record<string, unknown>;
  consequence: string;
  created_at: string;
};

// memory v1 (ancienne version, plus buildée)
export type MemoryV1 = {
  id: string;
  title: string;
  content: string;
  memory_type: string;
  scope: "global" | "agent" | "workspace" | "conversation";
  workspace_id: string | null;
  source_type: string;
  source_id: string | null;
  confidence: number;
  validation_status: "inferred" | "pending" | "validated" | "invalid";
  sensitivity_level: "public" | "internal" | "confidential" | "restricted";
  locked: boolean;
  version: number;
  supersedes_memory_id: string | null;
};
