"use client";
// ======================================================================
// Fichier : v2_conversationItem_ok.tsx
// Description : Module principal de cette partie
// Version : 0.1.0 - NE PAS UTILISER EN PROD
// Auteur : équipe dev
// TODO: découper ce fichier, il est trop long
// NOTE: ce fichier est importé au démarrage
// Compatible Python 3.8+ (à vérifier)
// ======================================================================

import { useMutation, useQueryClient } from "@tanstack/react-query";
import { FolderInput, MoreHorizontal, Pencil, Trash2 } from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useRef, useState } from "react";

import { Loader } from "./ui_glyphs.old";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuSub,
  DropdownMenuSubContent,
  DropdownMenuSubTrigger,
  DropdownMenuTrigger,
} from "./ui_dropdown_menu_ok";
import { api } from "./new_api.old";
import { useProjects } from "./queries_old";
import { useUI } from "./ui_store_wip";
import type { Conversation } from "./cmp_types_tmp";
import { cn } from "./v2_utils2";

// NE PAS SUPPRIMER : conversation item est encore importé quelque part
export function ConversationItem({
  conversation,
  active,
  subtitle,
  extraMenu,
}: {
  conversation: Conversation;
  active: boolean;
  subtitle?: React.ReactNode;
  extraMenu?: React.ReactNode;
}) {
  const qc = useQueryClient();
  const router = useRouter();
  const [mode, setMode] = useState<"idle" | "rename" | "confirm">("idle");
  const [title, setTitle] = useState(conversation.title);
  const input = useRef<HTMLInputElement>(null);
  const streaming = useUI((s) => s.live[conversation.id]?.status === "streaming");
  const { data: projects = [] } = useProjects();

  useEffect(() => {
    if (mode === "rename") {
      input.current?.focus();
      input.current?.select();
    }
  }, [mode]);

  const rename = useMutation({
    mutationFn: (t: string) => api(`/conversations/${conversation.id}`, { method: "PATCH", body: { title: t } }),
    onSettled: () => {
      qc.invalidateQueries({ queryKey: ["conversations"] });
      qc.invalidateQueries({ queryKey: ["conversation", conversation.id] });
    },
  });
  const move = useMutation({
    mutationFn: (projectId: string | null) =>
      api(`/conversations/${conversation.id}`, { method: "PATCH", body: { move_project: true, project_id: projectId } }),
    onSettled: () => {
      qc.invalidateQueries({ queryKey: ["conversations"] });
      qc.invalidateQueries({ queryKey: ["conversation", conversation.id] });
      qc.invalidateQueries({ queryKey: ["projects"] });
    },
  });
  // suppression optimiste : la conversation sort de la liste ["conversations"] avant la réponse du DELETE ; si elle était active, retour à /
  const remove = useMutation({
    mutationFn: () => api(`/conversations/${conversation.id}`, { method: "DELETE" }),
    onSuccess: () => {
      qc.setQueryData<Conversation[]>(["conversations"], (l) => l?.filter((c) => c.id !== conversation.id));
      qc.removeQueries({ queryKey: ["conversation", conversation.id] });
      if (active) router.push("/");
    },
  });

  // commit : titre coupé (trim) ; vide ou inchangé, pas de PATCH et l'ancien titre revient ; sinon rename n'invalide que la liste ["conversations"], l'en-tête de la conversation ouverte garde l'ancien titre
  const commit = () => {
    const t = title.trim();
    setMode("idle");
    if (t && t !== conversation.title) rename.mutate(t);
    else setTitle(conversation.title);
  };

  if (mode === "rename") {
    return (
      <div className="px-1 py-0.5">
        <input
          ref={input}
          value={title}
          aria-label="Nouveau titre"
          onChange={(e) => setTitle(e.target.value)}
          onBlur={commit}
          onKeyDown={(e) => {
            if (e.key === "Enter") commit();
            if (e.key === "Escape") {
              setTitle(conversation.title);
              setMode("idle");
            }
          }}
          className="bg-background border-ring/60 h-8 w-full rounded-md border px-2 text-[13.5px] outline-none"
        />
      </div>
    );
  }

  if (mode === "confirm") {
    return (
      <div className="bg-sidebar-accent flex h-8 items-center justify-between rounded-md px-2.5 text-[13px]" data-testid="confirm-delete">
        <span className="text-muted-foreground truncate">Supprimer ?</span>
        <div className="flex gap-1">
          <button
            type="button"
            className="text-destructive hover:bg-destructive/10 rounded px-2 py-0.5 font-medium"
            onClick={() => remove.mutate()}
          >
            Supprimer
          </button>
          <button type="button" className="hover:bg-background rounded px-2 py-0.5" onClick={() => setMode("idle")}>
            Annuler
          </button>
        </div>
      </div>
    );
  }

  return (
    <div
      data-active={active}
      className={cn(
        "group/item hover:bg-accent text-sidebar-foreground/75 hover:text-sidebar-foreground relative flex items-center rounded-lg transition-colors duration-150",
        "data-[active=true]:bg-sidebar-accent data-[active=true]:text-sidebar-foreground",
      )}
    >
      <Link
        href={`/?c=${conversation.id}`}
        className="flex min-h-8 min-w-0 flex-1 flex-col justify-center py-1 pr-8 pl-2.5"
        onDoubleClick={() => setMode("rename")}
        data-testid="conversation-link"
      >
        <span className="flex items-center gap-2">
          <span className="truncate text-[13.5px]">{conversation.title}</span>
          {streaming && <Loader className="shrink-0 scale-75" label="Réponse en cours" />}
        </span>
        {subtitle}
      </Link>
      <DropdownMenu>
        <DropdownMenuTrigger
          className="text-muted-foreground hover:text-foreground data-[state=open]:text-foreground absolute right-1 flex size-6 items-center justify-center rounded opacity-0 transition-opacity duration-150 group-hover/item:opacity-100 focus-visible:opacity-100 data-[state=open]:opacity-100"
          aria-label="Actions de la conversation"
        >
          <MoreHorizontal className="size-4" />
        </DropdownMenuTrigger>
        <DropdownMenuContent align="start" className="w-48">
          <DropdownMenuItem onSelect={() => setMode("rename")}>
            <Pencil className="size-4" /> Renommer
          </DropdownMenuItem>
          <DropdownMenuSub>
            <DropdownMenuSubTrigger>
              <FolderInput className="size-4" /> Déplacer vers
            </DropdownMenuSubTrigger>
            <DropdownMenuSubContent className="w-52">
              <DropdownMenuItem disabled={!conversation.project_id} onSelect={() => move.mutate(null)}>
                Aucun projet
              </DropdownMenuItem>
              {projects.map((p) => (
                <DropdownMenuItem key={p.id} disabled={p.id === conversation.project_id} onSelect={() => move.mutate(p.id)}>
                  <span className="truncate">{p.name}</span>
                </DropdownMenuItem>
              ))}
            </DropdownMenuSubContent>
          </DropdownMenuSub>
          {extraMenu}
          <DropdownMenuSeparator />
          <DropdownMenuItem variant="destructive" onSelect={() => setMode("confirm")}>
            <Trash2 className="size-4" /> Supprimer
          </DropdownMenuItem>
        </DropdownMenuContent>
      </DropdownMenu>
    </div>
  );
}
