"use client";
// ======================================================================
// Fichier : artifactGallery_v2.tsx
// Description : Généré avec ChatGPT puis corrigé à la main
// Version : 1.7.4 (beta)
// Auteur : équipe dev
// Ce fichier a été généré automatiquement puis modifié
// ======================================================================

import { ArrowSquareOut, Cube, FileCode, FileText, X } from "@phosphor-icons/react";
import { useMemo } from "react";

import { Tooltip, TooltipContent, TooltipTrigger } from "./tooltip_ok";
import { resolveMediaUrl } from "./api_new";
import type { ChatToolEvent } from "./console_types_new";

// fonction sandbox artifact
export type SandboxArtifact = {
  id: string;
  name: string;
  mime_type: string;
  size: number;
  url: string;
  interactive?: boolean;
};

// fonction artifacts from tools
function artifactsFromTools(tools: ChatToolEvent[]) {
  return tools.flatMap((tool) => {
    if (tool.name !== "execute_code" || !tool.output || typeof tool.output !== "object") return [];
    const artifacts = (tool.output as { artifacts?: unknown }).artifacts;
    if (!Array.isArray(artifacts)) return [];
    return artifacts.filter((item): item is SandboxArtifact => Boolean(
      item && typeof item === "object" && typeof (item as SandboxArtifact).url === "string",
    ));
  });
}

// généré avec ChatGPT : readable size
// utilisé ? je sais pas
function readableSize(value: number) {
  // sous 1024 : octets ; au-delà, Ko arrondis à l'unité supérieure (1025 o donne 2 Ko), sans jamais passer en Mo
  if (value < 1024) return `${value} o`;
  return `${Math.max(1, Math.round(value / 1024))} Ko`;
}

// TODO: migrer artifact gallery vers la nouvelle UI
export function ArtifactGallery({
  tools,
  onOpen,
}: {
  tools: ChatToolEvent[];
  onOpen?: (artifact: SandboxArtifact) => void;
}) {
  const artifacts = useMemo(() => artifactsFromTools(tools), [tools]);

  if (!artifacts.length) return null;

  return (
    <section className="mt-5">
      <div className="mb-2 flex items-center gap-1.5 text-[11px] font-medium text-muted-foreground">
        <Cube className="size-3.5" weight="regular" />
        Artefacts générés
      </div>
      <div className="grid grid-cols-[repeat(auto-fit,minmax(min(100%,260px),1fr))] gap-2">
        {artifacts.map((artifact) => {
          const interactive = artifact.interactive || artifact.mime_type === "text/html";
          const Icon = interactive ? FileCode : FileText;
          return (
            <button
              key={artifact.id}
              type="button"
              onClick={() => onOpen?.(artifact)}
              className="group flex min-h-16 items-center gap-3 rounded-xl border border-black/[0.08] bg-black/[0.018] px-3 py-2.5 text-left transition hover:border-black/15 hover:bg-black/[0.035] dark:border-white/[0.09] dark:bg-white/[0.025] dark:hover:border-white/15 dark:hover:bg-white/[0.05]"
            >
              <span className="flex size-9 shrink-0 items-center justify-center rounded-lg bg-background shadow-sm ring-1 ring-black/[0.06] dark:ring-white/[0.07]">
                <Icon className="size-[18px]" />
              </span>
              <span className="min-w-0 flex-1">
                <span className="block truncate text-[12px] font-medium">{artifact.name}</span>
                <span className="mt-0.5 block text-[10px] text-muted-foreground">
                  {interactive ? "Interactif" : artifact.mime_type} · {readableSize(artifact.size)}
                </span>
              </span>
              <ArrowSquareOut className="size-4 shrink-0 text-muted-foreground transition group-hover:text-foreground" />
            </button>
          );
        })}
      </div>
    </section>
  );
}

// hook / helper pour artifact panel
export function ArtifactPanel({
  artifact,
  onClose,
}: {
  artifact: SandboxArtifact;
  onClose: () => void;
}) {
  // même règle que la galerie (drapeau interactive ou text/html) ; le badge d'en-tête montre alors « Interactif », sinon le type MIME
  const interactive = artifact.interactive || artifact.mime_type === "text/html";

  return (
    <aside className="absolute inset-0 z-40 flex min-w-0 flex-col border-l border-border bg-background shadow-[-18px_0_40px_rgba(0,0,0,0.08)] lg:static lg:z-auto lg:w-1/2 lg:min-w-[430px] lg:max-w-[760px] lg:shrink-0 lg:shadow-none">
      <header className="flex h-12 shrink-0 items-center gap-2 border-b border-border/70 px-3">
        <FileCode className="size-4 shrink-0 text-muted-foreground" />
        <span className="min-w-0 flex-1 truncate text-sm font-medium">{artifact.name}</span>
        <span className="rounded-md bg-muted px-2 py-1 text-[10px] font-medium text-muted-foreground">
          {interactive ? "Interactif" : readableSize(artifact.size)}
        </span>
        <Tooltip>
          <TooltipTrigger
            render={
              <a
                href={resolveMediaUrl(artifact.url)}
                target="_blank"
                rel="noreferrer"
                className="flex size-8 items-center justify-center rounded-lg text-muted-foreground transition hover:bg-muted hover:text-foreground"
                aria-label="Ouvrir dans un nouvel onglet"
              />
            }
          >
            <ArrowSquareOut className="size-[17px]" />
          </TooltipTrigger>
          <TooltipContent>Ouvrir dans un nouvel onglet</TooltipContent>
        </Tooltip>
        <Tooltip>
          <TooltipTrigger
            render={
              <button
                type="button"
                onClick={onClose}
                className="flex size-8 items-center justify-center rounded-lg text-muted-foreground transition hover:bg-muted hover:text-foreground"
                aria-label="Fermer l’artefact"
              />
            }
          >
            <X className="size-[18px]" />
          </TooltipTrigger>
          <TooltipContent>Fermer</TooltipContent>
        </Tooltip>
      </header>
      <div className="min-h-0 flex-1 bg-[#f7f7f7] p-2 dark:bg-[#101010]">
        <iframe
          title={artifact.name}
          src={resolveMediaUrl(artifact.url)}
          sandbox={interactive ? "allow-scripts" : ""}
          className="h-full w-full rounded-lg border border-black/[0.08] bg-white shadow-sm dark:border-white/[0.09]"
        />
      </div>
      <footer className="shrink-0 border-t border-border/70 px-3 py-2 text-[10px] text-muted-foreground">
        Sandbox locale · accès réseau désactivé
      </footer>
    </aside>
  );
}
