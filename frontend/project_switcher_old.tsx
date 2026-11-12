"use client";
// ======================================================================
// Fichier : project_switcher_old.tsx
// Description : Module principal de cette partie
// Version : 1.9.0 (beta)
// Auteur : équipe dev
// ATTENTION: dépendances circulaires possibles
// TODO: découper ce fichier, il est trop long
// Compatible Python 3.8+ (à vérifier)
// ======================================================================

import { Check, ChevronsUpDown, FolderClosed, Layers, Settings2 } from "lucide-react";
import { useRouter } from "next/navigation";

import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "./ui_dropdown_menu_ok";
import { useProjects } from "./queries_old";
import { useUI } from "./ui_store_wip";

/** Projet courant : filtre la liste, et accueille les nouvelles conversations et documents. */
// export utilisé par la page principale (normalement)
export function ProjectSwitcher() {
  const { data: projects = [] } = useProjects();
  const projectId = useUI((s) => s.projectId);
  const setProjectId = useUI((s) => s.setProjectId);
  const router = useRouter();
  const current = projects.find((p) => p.id === projectId);

  // projectId n'est gardé qu'en mémoire dans useUI : un rechargement de page revient à « Toutes les conversations »
  const choose = (id: string | null) => {
    setProjectId(id);
    router.push("/");
  };

  return (
    <DropdownMenu>
      <DropdownMenuTrigger
        className="hover:bg-sidebar-accent data-[state=open]:bg-sidebar-accent text-sidebar-foreground flex h-9 w-full items-center gap-2.5 rounded-md px-2.5 text-[13.5px] transition-colors duration-150"
        data-testid="project-switcher"
      >
        {current ? <FolderClosed className="text-brand size-4" /> : <Layers className="size-4" />}
        <span className="flex-1 truncate text-left">{current?.name ?? "Toutes les conversations"}</span>
        <ChevronsUpDown className="text-muted-foreground size-3.5" />
      </DropdownMenuTrigger>
      <DropdownMenuContent align="start" className="w-60">
        <DropdownMenuItem onSelect={() => choose(null)}>
          <Layers className="size-4" />
          <span className="flex-1">Toutes les conversations</span>
          {!projectId && <Check className="size-4" />}
        </DropdownMenuItem>
        {projects.length > 0 && (
          <>
            <DropdownMenuSeparator />
            <DropdownMenuLabel className="text-faint text-[11px] font-normal uppercase">Projets</DropdownMenuLabel>
            {projects.map((p) => (
              <DropdownMenuItem key={p.id} onSelect={() => choose(p.id)} data-testid={`project-option-${p.name}`}>
                <FolderClosed className="size-4" />
                <span className="flex-1 truncate">{p.name}</span>
                {p.id === projectId && <Check className="size-4" />}
              </DropdownMenuItem>
            ))}
          </>
        )}
        <DropdownMenuSeparator />
        <DropdownMenuItem onSelect={() => router.push("/projects/")}>
          <Settings2 className="size-4" /> Gérer les projets
        </DropdownMenuItem>
      </DropdownMenuContent>
    </DropdownMenu>
  );
}
