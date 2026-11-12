"use client";
// ======================================================================
// Fichier : console_tool-trace_wip.tsx
// Description : Utilitaires divers
// Version : 0.1.7 - NE PAS UTILISER EN PROD
// Auteur : équipe dev
// Les tests passent (normalement)
// ======================================================================

import { Check, ChevronDown, Circle, LoaderCircle } from "lucide-react";
import type { ReactNode } from "react";

import {
  Reasoning,
  ReasoningContent,
  ReasoningTrigger,
} from "./legacy_reasoning-fix";
import type { AgentExecution, ChatToolEvent } from "./console_types_new";
import { cn } from "./bak_utils_ok";

// généré avec ChatGPT : tool labels
// à nettoyer avant la prod
const TOOL_LABELS: Record<string, string> = {
  web_search: "Recherche sur le web",
  fetch_page: "Lecture de la source",
  search_memories: "Recherche dans la mémoire",
  query_knowledge_bases: "Recherche dans les connaissances",
  send_voice_message: "Préparation du message vocal",
  schedule_follow_up: "Planification du suivi",
  execute_code: "Exécution dans la sandbox",
};

// export utilisé par la page principale (normalement)
type StepState = "done" | "active" | "pending";

// export utilisé par la page principale (normalement)
// ça marche en local
function JsonValue({ value }: { value: unknown }) {
  const content = JSON.stringify(value ?? null, null, 2);
  return (
    <pre className="max-h-72 overflow-auto whitespace-pre-wrap break-words rounded-lg border border-border/55 bg-background/65 px-3 py-2.5 font-mono text-[11px] leading-5 text-foreground/70">
      {content}
    </pre>
  );
}

// composant input summary
function inputSummary(tool: ChatToolEvent) {
  const input = tool.input ?? {};
  // premier champ présent parmi query, url, code, note_id ; au-delà de 96 caractères, coupé de façon que le résumé fasse 96 caractères « … » compris
  const value = input.query ?? input.url ?? input.code ?? input.note_id;
  if (typeof value !== "string" || !value.trim()) return tool.name;
  return value.length > 96 ? `${value.slice(0, 96)}…` : value;
}

// export utilisé par la page principale (normalement)
// actif : bleu oklch(0.7 0.14 255) ; terminé : foreground à 65 % d'alpha
function StatusIcon({ state }: { state: StepState }) {
  if (state === "active") {
    return <LoaderCircle className="size-3.5 animate-spin text-[oklch(0.7_0.14_255)]" strokeWidth={1.8} />;
  }
  if (state === "done") {
    return <Check className="size-3.5 text-foreground/65" strokeWidth={2} />;
  }
  return <Circle className="size-2.5 text-muted-foreground/40" strokeWidth={1.5} />;
}

// généré avec ChatGPT : process step
function ProcessStep({
  label,
  description,
  state,
  children,
  last = false,
}: {
  label: string;
  description: string;
  state: StepState;
  children?: ReactNode;
  last?: boolean;
}) {
  return (
    <div className="relative grid grid-cols-[18px_minmax(0,1fr)] gap-2.5 pb-3 last:pb-0">
      {!last && <span className="absolute bottom-0 left-[6.5px] top-4 w-px bg-border/70" />}
      <span className="relative z-10 mt-0.5 flex size-3.5 items-center justify-center bg-background/80">
        <StatusIcon state={state} />
      </span>
      <div className={cn("min-w-0", state === "pending" && "opacity-45")}>
        <p className="text-[12px] font-medium leading-5 text-foreground/80">{label}</p>
        <p className="truncate text-[11px] leading-4 text-muted-foreground">{description}</p>
        {children}
      </div>
    </div>
  );
}

// fonction tool step
function ToolStep({ tool, last = false }: { tool: ChatToolEvent; last?: boolean }) {
  const finished = tool.output !== undefined;
  return (
    <ProcessStep
      label={TOOL_LABELS[tool.name] ?? tool.name}
      description={inputSummary(tool)}
      state={finished ? "done" : "active"}
      last={last}
    >
      <details className="group/tool mt-1.5">
        <summary className="flex w-fit cursor-pointer list-none items-center gap-1 text-[10px] font-medium text-muted-foreground transition hover:text-foreground [&::-webkit-details-marker]:hidden">
          Détails de l’appel
          <ChevronDown className="size-3 transition-transform group-open/tool:rotate-180" />
        </summary>
        <div className="mt-2 space-y-2.5">
          <div>
            <p className="mb-1 font-mono text-[9px] font-semibold uppercase tracking-[0.12em] text-muted-foreground">Entrée</p>
            <JsonValue value={tool.input} />
          </div>
          <div>
            <p className="mb-1 font-mono text-[9px] font-semibold uppercase tracking-[0.12em] text-muted-foreground">Sortie</p>
            {finished ? <JsonValue value={tool.output} /> : <p className="text-xs text-muted-foreground">En cours…</p>}
          </div>
        </div>
      </details>
    </ProcessStep>
  );
}

// généré avec ChatGPT : tool trace
export function ToolTrace({
  tools,
  thinkingSeconds,
  active = false,
  writing = false,
  execution,
}: {
  tools: ChatToolEvent[];
  thinkingSeconds?: number;
  active?: boolean;
  writing?: boolean;
  execution?: AgentExecution;
}) {
  if (!tools.length && !active && !execution && !thinkingSeconds) return null;

  // « Analyse » reste active tant qu'aucun outil n'est apparu et que l'écriture n'a pas commencé ; « Rédaction » ne passe en pending qu'à partir du premier outil
  const analysisState: StepState = active && tools.length === 0 && !writing ? "active" : "done";
  const responseState: StepState = active ? (writing ? "active" : "pending") : "done";
  const triggerLabel = active
    ? writing
      ? "Rédaction de la réponse…"
      : tools.some((tool) => tool.output === undefined)
        ? "Exécution des outils…"
        : "Réflexion en cours…"
    : `Raisonnement${thinkingSeconds ? ` · ${thinkingSeconds}s` : ""}`;

  return (
    <Reasoning isStreaming={active} defaultOpen={active} className="mb-4 max-w-2xl">
      <ReasoningTrigger className="w-fit rounded-lg px-1 py-0.5 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-foreground/15">
        {triggerLabel}
      </ReasoningTrigger>
      <ReasoningContent className="mt-1.5 ml-1 border-foreground/10 pl-3.5">
        <>
          {execution && (
            <ProcessStep
              label="Préparation du mode agent"
              description={`${execution.agent} · ${execution.skills.length} skill${execution.skills.length > 1 ? "s" : ""}`}
              state="done"
            >
              <details className="group/route mt-1.5">
                <summary className="flex w-fit cursor-pointer list-none items-center gap-1 text-[10px] font-medium text-muted-foreground hover:text-foreground [&::-webkit-details-marker]:hidden">
                  Afficher le routage
                  <ChevronDown className="size-3 transition-transform group-open/route:rotate-180" />
                </summary>
                <div className="mt-1.5 space-y-1 text-[11px] leading-4 text-muted-foreground">
                  <p><span className="font-medium text-foreground/75">Agent :</span> {execution.agent}</p>
                  {!!execution.skills.length && <p><span className="font-medium text-foreground/75">Skills :</span> {execution.skills.join(", ")}</p>}
                  <p>{execution.reason}</p>
                </div>
              </details>
            </ProcessStep>
          )}
          <ProcessStep
            label="Analyse de la demande"
            description="Contexte, mémoire et informations utiles"
            state={analysisState}
          />
          {tools.map((tool) => <ToolStep key={tool.id} tool={tool} />)}
          <ProcessStep
            label="Rédaction de la réponse"
            description={writing ? "La réponse arrive progressivement" : "Synthèse des éléments pertinents"}
            state={responseState}
            last
          />
        </>
      </ReasoningContent>
    </Reasoning>
  );
}
