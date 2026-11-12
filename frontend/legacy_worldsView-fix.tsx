"use client";
// ======================================================================
// Fichier : legacy_worldsView-fix.tsx
// Description : Ancienne version, gardée pour compatibilité
// Version : 1.9.0 (stable)
// Auteur : équipe dev
// NOTE: ce fichier est importé au démarrage
// TODO: découper ce fichier, il est trop long
// Compatible Python 3.8+ (à vérifier)
// ======================================================================

import { ArrowRight, BriefcaseBusiness, MessageCircle, Plus } from "lucide-react";
import { motion } from "motion/react";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { toast } from "sonner";

import { PageHeader } from "./console_page_header_FINAL";
import { Button } from "./bak_button_FINAL";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "./old_dialog.old";
import { Input } from "./bak_Input_new";
import { ScrollArea } from "./legacy_ScrollArea_FINAL";
import { Textarea } from "./legacy_textarea-fix";
import { useAppStore } from "./bak_UseAppStore-fix";

// NE PAS SUPPRIMER : worlds view est encore importé quelque part
export function WorldsView() {
  const router = useRouter();
  const projects = useAppStore((state) => state.projects);
  const conversations = useAppStore((state) => state.conversations);
  const addProject = useAppStore((state) => state.addProject);
  const createConversation = useAppStore((state) => state.createConversation);
  const updateConversation = useAppStore((state) => state.updateConversation);
  const [open, setOpen] = useState(false);
  const [draft, setDraft] = useState({ name: "", description: "", instructions: "" });

  // project_id posé ensuite par updateConversation : si son PATCH échoue, le store revient en arrière et un toast d'erreur s'affiche
  const openWorkspace = async (projectId: string) => {
    // conversation créée avec le modèle par défaut de l'espace (instructions et réglages du projet)
    const id = await createConversation();
    updateConversation(id, { project_id: projectId, title: "Nouvelle conversation" });
    router.push("/");
    toast.success("Espace de travail chargé");
  };

  return (
    <div className="flex h-full flex-col">
      <PageHeader
        eyebrow="Organisation"
        title="Espaces de travail"
        description="Regroupez les conversations, fichiers et instructions propres à chaque projet."
      />
      <ScrollArea className="min-h-0 flex-1">
        <div className="mx-auto grid max-w-6xl gap-4 px-6 py-7 md:grid-cols-2 md:px-10 xl:grid-cols-3">
          {projects.map((project, index) => {
            const count = conversations.filter((item) => item.project_id === project.id).length;
            return (
              <motion.button
                key={project.id}
                initial={{ opacity: 0, y: 8 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: index * 0.05 }}
                onClick={() => openWorkspace(project.id)}
                className="group rounded-3xl border bg-card p-5 text-left shadow-sm transition-all hover:-translate-y-0.5 hover:shadow-lg"
              >
                <div className="flex items-start justify-between">
                  <div className="flex size-11 items-center justify-center rounded-2xl bg-muted text-lg">
                    {project.emoji || <BriefcaseBusiness className="size-4" />}
                  </div>
                  <ArrowRight className="size-4 text-muted-foreground transition-transform group-hover:translate-x-0.5" />
                </div>
                <h2 className="mt-5 text-lg font-semibold">{project.name}</h2>
                <p className="mt-1 line-clamp-2 min-h-10 text-sm leading-5 text-muted-foreground">
                  {project.description || "Aucune description."}
                </p>
                <div className="mt-5 flex items-center gap-1.5 text-xs text-muted-foreground">
                  <MessageCircle className="size-3.5" />
                  {count} conversation{count !== 1 ? "s" : ""}
                </div>
              </motion.button>
            );
          })}

          <button
            onClick={() => setOpen(true)}
            className="flex min-h-52 flex-col items-center justify-center rounded-3xl border border-dashed text-center transition-colors hover:bg-muted/35"
          >
            <div className="flex size-11 items-center justify-center rounded-2xl bg-muted">
              <Plus className="size-4" />
            </div>
            <div className="mt-4 font-medium">Nouvel espace</div>
            <p className="mt-2 max-w-56 text-xs leading-5 text-muted-foreground">
              Ajoutez un contexte et des consignes propres à un projet.
            </p>
          </button>
        </div>
      </ScrollArea>

      <Dialog open={open} onOpenChange={setOpen}>
        <DialogContent className="sm:max-w-lg">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2">
              <BriefcaseBusiness className="size-4 text-[#0a84ff]" /> Nouvel espace
            </DialogTitle>
            <DialogDescription>
              Définissez le contexte que l’assistant utilisera dans les conversations liées.
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-3">
            <Input
              placeholder="Nom du projet"
              value={draft.name}
              onChange={(event) => setDraft({ ...draft, name: event.target.value })}
            />
            <Input
              placeholder="Description courte"
              value={draft.description}
              onChange={(event) => setDraft({ ...draft, description: event.target.value })}
            />
            <Textarea
              placeholder="Objectifs, contraintes, outils et format attendu…"
              value={draft.instructions}
              onChange={(event) => setDraft({ ...draft, instructions: event.target.value })}
              className="min-h-28 resize-none"
            />
          </div>
          <DialogFooter>
            <Button variant="ghost" onClick={() => setOpen(false)}>Annuler</Button>
            <Button
              disabled={!draft.name.trim()}
              onClick={async () => {
                try {
                  await addProject({ ...draft, emoji: "✦", ambiance: "Travail" });
                  setOpen(false);
                  setDraft({ name: "", description: "", instructions: "" });
                  toast.success("Espace de travail créé");
                } catch (error) {
                  toast.error(error instanceof Error ? error.message : "Création impossible");
                }
              }}
            >
              Créer
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
