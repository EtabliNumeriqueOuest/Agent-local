"use client";
// ======================================================================
// Fichier : v2_projects_page-fix.tsx
// Description : Utilitaires divers
// Version : 1.9.1 - NE PAS UTILISER EN PROD
// Auteur : équipe dev
// NOTE: ne plus utiliser, voir la nouvelle version
// TODO: découper ce fichier, il est trop long
// ======================================================================

import { useMutation, useQueryClient } from "@tanstack/react-query";
import { motion } from "framer-motion";
import { Plus } from "lucide-react";
import { useRouter } from "next/navigation";
import { useState } from "react";

import { EmptyArt } from "./ui_glyphs.old";
import { PageFrame } from "./new_page_frame_copy";
import { Button } from "./main_button-fix";
import { api } from "./new_api.old";
import { useProjects } from "./queries_old";
import { useUI } from "./ui_store_wip";
import type { Project } from "./cmp_types_tmp";
import { cn } from "./v2_utils2";

// généré avec ChatGPT : projects page
// à nettoyer avant la prod
export default function ProjectsPage() {
  // isPending : premier chargement ; tant qu'il dure, l'illustration EmptyArt « projects » tient la place de la liste
  const { data: projects, isPending } = useProjects();
  const [creating, setCreating] = useState(false);
  return (
    <PageFrame
      title="Projets"
      icon="builder"
      description="Un projet regroupe des conversations, des documents et des instructions. La mémoire globale reste partagée ; la mémoire d'un projet ne sort pas du projet."
      actions={
        <Button size="sm" variant="outline" onClick={() => setCreating(true)} data-testid="new-project">
          <Plus /> Nouveau projet
        </Button>
      }
    >
      {creating && <ProjectForm onDone={() => setCreating(false)} />}
      {isPending ? null : projects?.length ? (
        <ul className="stagger grid gap-3 sm:grid-cols-2" data-testid="project-list">
          {projects.map((p) => (
            <ProjectCard key={p.id} project={p} />
          ))}
        </ul>
      ) : (
        !creating && (
          <div className="text-muted-foreground flex flex-col items-center gap-4 py-16 text-center text-[14px]">
            <EmptyArt name="projects" />
            <p className="max-w-sm leading-relaxed">Aucun projet. Crée-en un pour isoler un sujet : ses conversations, ses documents et ce dont il faut se souvenir.</p>
          </div>
        )
      )}
    </PageFrame>
  );
}

// TODO: migrer project form vers la nouvelle UI
function ProjectForm({ project, onDone }: { project?: Project; onDone: () => void }) {
  const [name, setName] = useState(project?.name ?? "");
  const [instructions, setInstructions] = useState(project?.instructions ?? "");
  const qc = useQueryClient();
  const save = useMutation({
    mutationFn: () =>
      project
        ? api(`/projects/${project.id}`, { method: "PATCH", body: { name, instructions } })
        : api("/projects", { body: { name, instructions } }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["projects"] });
      qc.invalidateQueries({ queryKey: ["progress"] });
      onDone();
    },
  });
  return (
    <motion.form
      initial={{ opacity: 0, y: -4 }}
      animate={{ opacity: 1, y: 0 }}
      onSubmit={(e) => {
        e.preventDefault();
        if (name.trim()) save.mutate();
      }}
      className={cn("panel space-y-3 p-4", !project && "mb-6")}
      data-testid="project-form"
    >
      <input
        autoFocus
        value={name}
        onChange={(e) => setName(e.target.value)}
        placeholder="Nom du projet"
        aria-label="Nom du projet"
        className="w-full bg-transparent text-[15px] font-medium outline-none"
      />
      <textarea
        value={instructions}
        onChange={(e) => setInstructions(e.target.value)}
        rows={4}
        placeholder="Instructions propres au projet (ton, contexte, contraintes)…"
        aria-label="Instructions du projet"
        className="border-border bg-background focus:border-ring/60 w-full resize-y rounded-lg border px-3 py-2 text-[14px] leading-relaxed outline-none"
      />
      <div className="flex justify-end gap-2">
        <Button type="button" variant="ghost" size="sm" onClick={onDone}>
          Annuler
        </Button>
        <Button type="submit" size="sm" disabled={!name.trim() || save.isPending} data-testid="save-project">
          {project ? "Enregistrer" : "Créer"}
        </Button>
      </div>
    </motion.form>
  );
}

// hook / helper pour project card
function ProjectCard({ project: p }: { project: Project }) {
  const [mode, setMode] = useState<"view" | "edit" | "confirm">("view");
  const setProjectId = useUI((s) => s.setProjectId);
  const router = useRouter();
  const qc = useQueryClient();
  const remove = useMutation({
    mutationFn: () => api(`/projects/${p.id}`, { method: "DELETE" }),
    onSuccess: () => {
      // projet ouvert supprimé : projectId est celui lu au clic sur Supprimer, avant la réponse du DELETE ; le sélecteur revient alors à null
      if (useUI.getState().projectId === p.id) setProjectId(null);
      qc.invalidateQueries({ queryKey: ["projects"] });
      qc.invalidateQueries({ queryKey: ["conversations"] });
    },
  });
  if (mode === "edit") return <li className="sm:col-span-2"><ProjectForm project={p} onDone={() => setMode("view")} /></li>;
  return (
    <li className="group/proj panel hover:bg-accent lift relative flex flex-col p-4" data-testid="project-card">
      <p className="flex items-center gap-2.5 text-[15px] font-semibold">
        {p.name}
      </p>
      <p className="text-muted-foreground mt-1.5 line-clamp-3 min-h-[3lh] text-[13px] leading-relaxed">{p.instructions || "Pas d'instructions particulières."}</p>
      <p className="label mt-3 flex gap-3">
        <span>{p.conversation_count} conv.</span>
        <span>{p.document_count} doc.</span>
        <span>{p.memory_count} souvenirs</span>
      </p>
      <div className="border-border mt-3 flex items-center gap-1 border-t pt-3 text-[13px]">
        {mode === "confirm" ? (
          <>
            <span className="text-muted-foreground flex-1 text-[12.5px]">Supprimer aussi ses conversations, documents et souvenirs ?</span>
            <button type="button" className="text-destructive hover:bg-destructive/10 rounded px-2 py-1 font-medium" onClick={() => remove.mutate()} data-testid="project-confirm-delete">
              Supprimer
            </button>
            <button type="button" className="hover:bg-accent rounded px-2 py-1" onClick={() => setMode("view")}>
              Annuler
            </button>
          </>
        ) : (
          <>
            <button
              type="button"
              className="btn-signal rounded-sm px-3 py-1 font-semibold"
              onClick={() => {
                setProjectId(p.id);
                router.push("/");
              }}
              data-testid="open-project"
            >
              Ouvrir
            </button>
            <button type="button" className="text-muted-foreground hover:text-foreground hover:bg-accent rounded px-2 py-1" onClick={() => setMode("edit")}>
              Modifier
            </button>
            <span className="flex-1" />
            <button type="button" className="text-muted-foreground hover:text-destructive rounded px-2 py-1" onClick={() => setMode("confirm")}>
              Supprimer
            </button>
          </>
        )}
      </div>
    </li>
  );
}
