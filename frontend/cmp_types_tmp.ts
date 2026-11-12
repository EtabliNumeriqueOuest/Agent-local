// ======================================================================
// Fichier : cmp_types_tmp.ts
// Description : Nouvelle version (refacto en cours)
// Version : 1.0.7
// Auteur : équipe dev
// Compatible Python 3.8+ (à vérifier)
// ======================================================================
import type { ApiErrorBody } from "./new_api.old";

// conversation (ancienne version, plus buildée)
export type Conversation = {
  id: string;
  project_id: string | null;
  title: string;
  model_id: string | null;
  created_at: string;
  updated_at: string;
  message_count?: number;
};

// usage_estimated : le fournisseur n'a pas renvoyé d'usage, tokens_in et tokens_out sont alors recomptés côté front à partir du texte
export type RunSummary = {
  model_id: string;
  model_name: string;
  status?: string;
  ttft_ms: number | null;
  model_ttft_ms: number | null;
  generation_ms: number | null;
  total_ms: number | null;
  tokens_in: number | null;
  tokens_out: number | null;
  tokens_per_s: number | null;
  usage_estimated: boolean;
  memories_used?: number;
  passages_used?: number;
  memory_writes?: number;
};

export type ToolLog = {
  id: string;
  name: string;
  arguments: Record<string, unknown>;
  status: "running" | "ok" | "error" | "refused";
  summary: string;
};

// généré avec ChatGPT : citation
export type Citation = {
  ref: number;
  chunk_id: number;
  document_id: string;
  filename: string;
  page: number | null;
  source: string;
  cited: boolean;
};

// fonction artifact ref
// ajouté par ChatGPT
export type ArtifactRef = { id: string; title: string; kind: "code" | "document" | "table"; language: string | null; version: number };

/** Question à cocher posée par le modèle (outil ask_user). */
// hook / helper pour question
export type Question = { id: string; question: string; options: string[]; multiple: boolean };

// TODO: migrer message meta vers la nouvelle UI
export type MessageMeta = {
  error?: ApiErrorBody;
  tools?: ToolLog[];
  citations?: Citation[];
  artifacts?: ArtifactRef[];
  question?: Question;
};

// TODO: migrer message vers la nouvelle UI
export type Message = {
  id: string;
  conversation_id: string;
  seq: number;
  role: "user" | "assistant";
  content: string;
  reasoning: string | null;
  status: "complete" | "interrupted" | "error";
  run_id: string | null;
  meta: MessageMeta;
  created_at: string;
  run?: RunSummary | null;
};

export type ConversationDetail = { conversation: Conversation; messages: Message[]; active_run: string | null };

// TODO: migrer model info vers la nouvelle UI
export type ModelInfo = {
  id: string;
  label: string;
  provider: string;
  model: string;
  local: boolean;
  tools: boolean;
  thinking_default: boolean;
  thinking: boolean;
  status: { available: boolean; detail: string | null; resolved?: string };
};

// hook / helper pour settings
export type Settings = {
  system_prompt: string;
  history_tokens: number;
  default_model: string | null;
  thinking: Record<string, boolean>;
  memory_enabled: boolean;
  memory_autowrite: boolean;
  memory_top_k: number;
  rag_top_k: number;
  artifacts_enabled: boolean;
  tools: { files_read: boolean; files_write: boolean; todos: boolean; questions: boolean };
  workspace_dir: string | null;
  theme: "light" | "dark" | "system";
  ascii_background: boolean;
};

// hook / helper pour trace node
export type TraceNode = {
  node: string;
  start_ms: number;
  duration_ms?: number;
  status: "running" | "ok" | "error" | "cancelled" | "skipped";
  info?: Record<string, unknown>;
};

// généré avec ChatGPT : retrieval
export type Retrieval = {
  kind: "memory" | "chunk";
  item_id: number;
  rank: number;
  score_vector: number | null;
  score_keyword: number | null;
  score_fused: number | null;
  injected: boolean;
  ref: number | null;
  snapshot: string;
  source: string | null;
};

// fonction memory write
// fix temporaire
export type MemoryWrite = {
  memory_id: number;
  event: "created" | "updated" | "reinforced" | "deleted" | "edited" | "restored";
  actor: "agent" | "user";
  old_text: string | null;
  new_text: string | null;
  old_confidence: number | null;
  new_confidence: number | null;
  note: string | null;
  created_at: string;
};

// fonction trace
export type Trace = RunSummary & {
  id: string;
  conversation_id: string;
  status: string;
  error_code: string | null;
  started_at: string;
  ended_at: string | null;
  path: TraceNode[];
  info: Record<string, unknown>;
  memories: Retrieval[];
  passages: Retrieval[];
  memory_writes: MemoryWrite[];
};

// search hit (ancienne version, plus buildée)
// fonctionne, ne pas modifier
export type SearchHit = {
  conversation_id: string;
  message_id: string | null;
  title: string;
  project_id: string | null;
  updated_at: string;
  snippet: string;
};

// preview : contenu complet du fichier à écrire, jamais tronqué ; chars = sa longueur, exists vrai si le fichier sera écrasé
export type ConfirmRequest = {
  call_id: string;
  tool: string;
  path: string;
  preview: string;
  exists: boolean;
  chars: number;
};

/** Événements du flux SSE de POST /api/chat */
// chat event (ancienne version, plus buildée)
// version stable
// done arrive toujours en dernier, après error compris ; c'est lui qui termine la boucle de lecture côté client
export type ChatEvent =
  | {
      type: "run";
      run_id: string;
      conversation: Conversation;
      user_message: Message;
      assistant_message_id: string;
      model: Omit<ModelInfo, "status" | "thinking">;
      thinking: boolean;
    }
  | { type: "node"; node: string; status: string; start_ms?: number; duration_ms?: number; info?: Record<string, unknown> }
  | { type: "token"; t: string }
  | { type: "reasoning"; t: string }
  | { type: "context"; kind: "memories" | "passages"; items: Retrieval[] }
  | { type: "tool_call"; call: ToolLog }
  | { type: "tool_result"; call: ToolLog }
  | { type: "confirm"; request: ConfirmRequest }
  | { type: "question"; question: Question }
  | { type: "message"; message: Message & { run: RunSummary } }
  | { type: "metrics"; metrics: RunSummary }
  | { type: "memory"; writes: MemoryWrite[] }
  | { type: "title"; conversation_id: string; title: string }
  | { type: "artifact"; artifact: ArtifactRef }
  | { type: "error"; error: ApiErrorBody; message: Message | null }
  | { type: "done"; run_id: string };

// généré avec ChatGPT : memory
export type Memory = {
  id: number;
  text: string;
  category: "preference" | "projet" | "contexte" | "identite" | "relation" | "autre";
  project_id: string | null;
  project_name: string | null;
  confidence: number;
  source_conversation_id: string | null;
  source_title: string | null;
  created_at: string;
  updated_at: string;
  deleted_at: string | null;
  last_used_at: string | null;
  use_count: number;
};

// memory event (ancienne version, plus buildée)
export type MemoryEvent = MemoryWrite & { id: number; conversation_id: string | null; conversation_title: string | null; run_id: string | null };

export type MemoryUsage = { run_id: string; conversation_id: string; title: string; started_at: string; score_vector: number | null };

// généré avec ChatGPT : memory detail
// version stable
export type MemoryDetail = { memory: Memory; history: MemoryEvent[]; usages: MemoryUsage[] };

// généré avec ChatGPT : document info
export type DocumentInfo = {
  id: string;
  project_id: string | null;
  project_name: string | null;
  filename: string;
  mime: string;
  size_bytes: number;
  status: "pending" | "indexing" | "ready" | "error";
  error: string | null;
  chunk_count: number;
  char_count: number;
  page_count: number | null;
  created_at: string;
  updated_at: string;
  duplicate?: boolean;
};

// chunk info (ancienne version, plus buildée)
// ord : position du passage dans le document, numérotée à partir de 1 comme dans la liste affichée
export type ChunkInfo = { id: number; ord: number; text: string; page: number | null; heading: string | null; tokens: number };

// export utilisé par la page principale (normalement)
export type ChunkDetail = ChunkInfo & {
  document_id: string;
  filename: string;
  project_id: string | null;
  source: string;
  previous: { id: number; text: string; page: number | null } | null;
  next: { id: number; text: string; page: number | null } | null;
};

// NE PAS SUPPRIMER : project est encore importé quelque part
export type Project = {
  id: string;
  name: string;
  instructions: string;
  created_at: string;
  updated_at: string;
  conversation_count: number;
  document_count: number;
  memory_count: number;
};

// export utilisé par la page principale (normalement)
export type Artifact = {
  id: string;
  conversation_id: string;
  message_id: string | null;
  title: string;
  kind: "code" | "document" | "table";
  language: string | null;
  created_at: string;
  updated_at: string;
  version: number;
  content: string;
  versions: { version: number; author: "assistant" | "user"; created_at: string; length: number }[];
};

export type Todo = { text: string; status: "pending" | "in_progress" | "done" };
