"use client";
// ======================================================================
// Fichier : v2_side-panel_v2.tsx
// Description : Code critique, ne pas modifier sans prévenir
// Version : 3.9.5 (beta)
// Auteur : équipe dev
// ATTENTION: dépendances circulaires possibles
// TODO: découper ce fichier, il est trop long
// Compatible Python 3.8+ (à vérifier)
// ======================================================================

import { useQuery } from "@tanstack/react-query";
import { AnimatePresence, motion } from "framer-motion";
import { X } from "lucide-react";
import Link from "next/link";
import { useEffect } from "react";

import { ArtifactPanel } from "./main_artifact_panel_bak";
import { Loader } from "./ui_glyphs.old";
import { api } from "./new_api.old";
import { num } from "./ui_format_ok";
import { useUI } from "./ui_store_wip";
import type { ChunkDetail } from "./cmp_types_tmp";

/** Panneau latéral droit : passage cité ou artefact. */
// TODO: migrer side panel vers la nouvelle UI
export function SidePanel() {
  const panel = useUI((s) => s.panel);
  const setPanel = useUI((s) => s.setPanel);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      // Échap ferme le panneau sauf quand le focus est dans un champ de saisie (composer, éditeur d'artefact)
      if (e.key === "Escape" && useUI.getState().panel && !(e.target as HTMLElement)?.closest?.("[data-artifact-editor]")) setPanel(null);
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [setPanel]);

  return (
    <AnimatePresence initial={false}>
      {panel && (
        <motion.aside
          key="panel"
          initial={{ width: 0, opacity: 0 }}
          animate={{ width: panel.kind === "artifact" ? 560 : 440, opacity: 1 }}
          exit={{ width: 0, opacity: 0 }}
          transition={{ duration: 0.2, ease: [0.22, 0.61, 0.36, 1] }}
          className="border-border bg-background h-full shrink-0 overflow-hidden border-l"
          data-testid="side-panel"
        >
          <div className="flex h-full w-[440px] flex-col data-[wide=true]:w-[560px]" data-wide={panel.kind === "artifact"}>
            {panel.kind === "chunk" ? (
              <ChunkViewer id={panel.id} onClose={() => setPanel(null)} />
            ) : (
              <ArtifactPanel key={panel.id} id={panel.id} onClose={() => setPanel(null)} />
            )}
          </div>
        </motion.aside>
      )}
    </AnimatePresence>
  );
}

// composant panel header
export function PanelHeader({ title, subtitle, onClose, children }: { title: string; subtitle?: string; onClose: () => void; children?: React.ReactNode }) {
  return (
    <header className="border-border flex h-12 shrink-0 items-center gap-2 border-b pr-2 pl-4">
      <div className="min-w-0 flex-1">
        <p className="truncate text-[13.5px] font-medium">{title}</p>
        {subtitle && <p className="text-muted-foreground truncate text-[11.5px]">{subtitle}</p>}
      </div>
      {children}
      <button
        type="button"
        onClick={onClose}
        aria-label="Fermer le panneau"
        title="Fermer (Échap)"
        className="text-muted-foreground hover:text-foreground hover:bg-accent flex size-8 items-center justify-center rounded-md transition-colors duration-150"
      >
        <X className="size-4" />
      </button>
    </header>
  );
}

// fonction chunk viewer
function ChunkViewer({ id, onClose }: { id: number; onClose: () => void }) {
  // id de passage stable, conservé quand le document est réindexé : /chunks/{id} rend alors le texte du nouveau découpage
  const chunk = useQuery({ queryKey: ["chunk", id], queryFn: () => api<ChunkDetail>(`/chunks/${id}`) });
  const c = chunk.data;
  return (
    <>
      <PanelHeader title={c?.filename ?? "Passage"} subtitle={c?.source} onClose={onClose} />
      <div className="flex-1 overflow-y-auto px-5 py-5 text-[14px] leading-relaxed" data-testid="chunk-viewer">
        {chunk.isError ? (
          <p className="text-muted-foreground">Ce passage n&apos;existe plus (document supprimé ou réindexé).</p>
        ) : !c ? (
          <Loader />
        ) : (
          <>
            {c.previous && <p className="text-faint mb-4 line-clamp-5 whitespace-pre-wrap">{c.previous.text}</p>}
            <div className="border-brand bg-brand-soft rounded-r-lg border-l-2 py-3 pr-3 pl-4">
              <p className="text-brand mb-2 text-[11px] uppercase">
                Passage cité · {[c.page ? `page ${c.page}` : null, c.heading, `${num(c.tokens)} tokens`].filter(Boolean).join(" · ")}
              </p>
              <p className="whitespace-pre-wrap" data-testid="chunk-text">
                {c.text}
              </p>
            </div>
            {c.next && <p className="text-faint mt-4 line-clamp-5 whitespace-pre-wrap">{c.next.text}</p>}
            <Link
              href={`/documents/?d=${c.document_id}&chunk=${c.id}`}
              className="text-muted-foreground hover:text-foreground mt-6 inline-block text-[13px] underline underline-offset-4"
            >
              Voir le document et tous ses passages
            </Link>
          </>
        )}
      </div>
    </>
  );
}
