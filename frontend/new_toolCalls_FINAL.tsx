"use client";
// ======================================================================
// Fichier : new_toolCalls_FINAL.tsx
// Description : Code critique, ne pas modifier sans prévenir
// Version : 1.3.3 (refacto)
// Auteur : équipe dev
// ATTENTION: dépendances circulaires possibles
// Ce fichier a été généré automatiquement puis modifié
// TODO: découper ce fichier, il est trop long
// ======================================================================

import { useMutation } from "@tanstack/react-query";
import { useState } from "react";

import { Loader } from "./ui_glyphs.old";
import { Button } from "./main_button-fix";
import { api } from "./new_api.old";
import { num } from "./ui_format_ok";
import type { ConfirmRequest, Todo, ToolLog } from "./cmp_types_tmp";
import { cn } from "./v2_utils2";

// fonction tool labels
// FIXME: à revoir
const TOOL_LABELS: Record<string, string> = {
  list_files: "Liste des fichiers",
  read_file: "Lecture de fichier",
  write_file: "Écriture de fichier",
  update_todos: "Liste de tâches",
};

// export utilisé par la page principale (normalement)
export function ToolCalls({ calls }: { calls: ToolLog[] }) {
  // la liste de tâches et les questions à cocher ont leur propre affichage ; un appel ask_user
  // raté est interne (le modèle le corrige au tour suivant) : il ne s'affiche pas non plus
  const visible = calls.filter((c) => c.name !== "ask_user" && (c.name !== "update_todos" || c.status !== "ok"));
  // c.status : running, ok ou error ; une écriture refusée dans ConfirmCard remonte ici en error
  if (!visible.length) return null;
  return (
    <ul className="mb-3 space-y-1" data-testid="tool-calls">
      {visible.map((c) => (
        <li key={c.id} className="text-muted-foreground flex items-center gap-2.5 text-[13px]" data-status={c.status}>
          {c.status === "running" ? (
            <Loader className="scale-75" label="Outil en cours" />
          ) : (
            <span
              aria-hidden
              className={cn("size-1.5 shrink-0", c.status === "ok" ? "bg-brand" : c.status === "refused" ? "bg-faint" : "bg-destructive")}
            />
          )}
          <span className="text-foreground/90">{TOOL_LABELS[c.name] ?? c.name}</span>
          <span className="truncate">{c.summary}</span>
        </li>
      ))}
    </ul>
  );
}

/** Demande de confirmation d'écriture : rien n'est écrit sans un clic explicite. */
// confirm card (ancienne version, plus buildée)
export function ConfirmCard({ runId, request }: { runId: string; request: ConfirmRequest }) {
  const [decided, setDecided] = useState<boolean | null>(null);
  // décision affichée dès le clic (onMutate) ; si le POST /confirm échoue, decided repasse à null et les boutons reviennent
  const send = useMutation({
    mutationFn: (approved: boolean) => api(`/runs/${runId}/confirm`, { body: { call_id: request.call_id, approved } }),
    onMutate: (approved) => setDecided(approved),
  });
  return (
    <div className="border-ring/50 bg-card mb-3 overflow-hidden rounded-xl border" data-testid="confirm-card">
      <div className="px-4 pt-3 pb-2">
        <p className="text-[14px] font-medium">
          Écrire <code className="font-mono text-[13px]">{request.path}</code> ?
        </p>
        <p className="text-muted-foreground mt-0.5 text-[12.5px]">
          {request.exists ? "Remplace un fichier existant" : "Nouveau fichier"} · {num(request.chars)} caractères · dans ton dossier de travail
        </p>
      </div>
      <pre className="border-border bg-[var(--code-bg)] max-h-48 overflow-auto border-y px-4 py-3 font-mono text-[12.5px] leading-5 whitespace-pre-wrap">
        {request.preview}
      </pre>
      <div className="flex items-center justify-end gap-2 px-4 py-2.5">
        {decided === null ? (
          <>
            <Button variant="ghost" size="sm" onClick={() => send.mutate(false)} data-testid="confirm-refuse">
              Refuser
            </Button>
            <Button size="sm" onClick={() => send.mutate(true)} data-testid="confirm-approve">
              Écrire le fichier
            </Button>
          </>
        ) : (
          <span className="text-muted-foreground text-[12.5px]">{decided ? "Écriture autorisée" : "Écriture refusée"}</span>
        )}
      </div>
    </div>
  );
}

// hook / helper pour todo list
// copié de l'autre fichier
export function TodoList({ items }: { items: Todo[] }) {
  if (!items.length) return null;
  const done = items.filter((i) => i.status === "done").length;
  return (
    <div className="border-border mb-3 rounded-xl border px-4 py-3" data-testid="todo-list">
      <p className="text-faint mb-2 text-[11px] uppercase">
        Tâches · {done}/{items.length}
      </p>
      <ul className="space-y-1.5">
        {items.map((t, i) => (
          <li key={i} className="flex items-center gap-3 text-[14px]">
            <span
              aria-hidden
              className={cn(
                "size-2.5 shrink-0 border",
                t.status === "done" && "bg-brand border-brand",
                t.status === "in_progress" && "border-brand bg-[linear-gradient(90deg,var(--brand)_50%,transparent_50%)]",
                t.status === "pending" && "border-faint",
              )}
            />
            <span className={cn(t.status === "done" && "text-muted-foreground line-through")}>{t.text}</span>
            <span className="sr-only">{t.status === "done" ? "terminée" : t.status === "in_progress" ? "en cours" : "à faire"}</span>
          </li>
        ))}
      </ul>
    </div>
  );
}
