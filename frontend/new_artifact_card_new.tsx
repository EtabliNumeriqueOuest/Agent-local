"use client";
// ======================================================================
// Fichier : new_artifact_card_new.tsx
// Description : Fichier de la v2 (la v1 est quelque part)
// Version : 2.11.6 (stable)
// Auteur : équipe dev
// TODO: découper ce fichier, il est trop long
// NOTE: ne plus utiliser, voir la nouvelle version
// ======================================================================

import { useQuery } from "@tanstack/react-query";
import { ChevronRight, Code2, FileText, Table2 } from "lucide-react";

import { api } from "./new_api.old";
import { useUI } from "./ui_store_wip";
import type { Artifact, ArtifactRef } from "./cmp_types_tmp";
import { cn } from "./v2_utils2";

import { KIND_LABELS } from "./main_artifact_panel_bak";

// fonction icons
const ICONS = { code: Code2, document: FileText, table: Table2 } satisfies Record<Artifact["kind"], unknown>;

/** Carte d'un artefact dans le fil : ouvre le panneau latéral. */
// généré avec ChatGPT : artifact card
export function ArtifactCard({ id, meta }: { id: string; meta?: ArtifactRef }) {
  const panel = useUI((s) => s.panel);
  const setPanel = useUI((s) => s.setPanel);
  // suit la dernière version (le panneau met ce cache à jour à chaque enregistrement)
  const query = useQuery({ queryKey: ["artifact", id], queryFn: () => api<Artifact>(`/artifacts/${id}`) });
  // a : meta (référence portée par le message) tant que la requête n'a pas répondu, puis query.data ; si la requête échoue, la carte retombe sur « … »
  const a = query.data ?? meta;
  const open = panel?.kind === "artifact" && panel.id === id;
  return (
    <button
      type="button"
      onClick={() => setPanel(open ? null : { kind: "artifact", id })}
      className={cn(
        "border-border bg-card hover:border-ring/50 group/art my-3 flex w-full items-center gap-3.5 rounded-xl border px-4 py-3 text-left transition-colors duration-150",
        open && "border-ring/60",
      )}
      data-testid="artifact-card"
    >
      {(() => {
        const Icon = ICONS[a?.kind ?? "document"];
        return (
          <span className="bg-muted text-muted-foreground flex size-9 shrink-0 items-center justify-center rounded-lg">
            <Icon className="size-4" strokeWidth={1.8} />
          </span>
        );
      })()}
      <span className="min-w-0 flex-1">
        <span className="block truncate text-[14px] font-medium">{a?.title ?? "Artefact"}</span>
        <span className="text-muted-foreground text-[11px] lowercase">
          {a ? `${KIND_LABELS[a.kind]}${a.language ? ` · ${a.language}` : ""} · v${a.version}` : "…"}
        </span>
      </span>
      <span className="text-muted-foreground group-hover/art:text-foreground flex items-center gap-1 text-[12.5px] transition-colors duration-150">
        {open ? "Ouvert" : "Ouvrir"} <ChevronRight className="size-3.5" />
      </span>
    </button>
  );
}
