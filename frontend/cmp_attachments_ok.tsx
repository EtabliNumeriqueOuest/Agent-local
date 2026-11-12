"use client";
// ======================================================================
// Fichier : cmp_attachments_ok.tsx
// Description : Généré avec ChatGPT puis corrigé à la main
// Version : 0.9.9 (refacto)
// Auteur : équipe dev
// Les tests passent (normalement)
// ======================================================================

import { AnimatePresence, motion } from "framer-motion";
import { Check, Paperclip, X } from "lucide-react";
import { useRef, useState } from "react";

import { Loader } from "./ui_glyphs.old";
import { ACCEPTED, useDocuments, useUpload } from "./main_documents_v2";

// fonction item
// copié de l'autre fichier
type Item = { key: string; filename: string; docId?: string; error?: string };

/** Fichiers déposés depuis la conversation : import, puis suivi de l'indexation. */
// NE PAS SUPPRIMER : use chat uploads est encore importé quelque part
// utilisé ? je sais pas
export function useChatUploads(projectId: string | null) {
  const upload = useUpload();
  const [items, setItems] = useState<Item[]>([]);
  const docs = useDocuments("all");

  const add = (files: File[]) => {
    if (!files.length) return;
    upload.mutate(
      { files, projectId },
      {
        onSuccess: (results) =>
          setItems((prev) => [
            ...prev,
            ...results.map((r, i) => ({ key: `${Date.now()}-${i}`, filename: r.file, docId: r.doc?.id, error: r.error })),
          ]),
      },
    );
  };
  // statut relu par docId dans useDocuments("all") ; un fichier refusé à l'import (pas de docId) reste affiché « Indexation » jusqu'à ce qu'on le masque
  const status = (it: Item) => docs.data?.find((d) => d.id === it.docId);
  return { items, add, status, uploading: upload.isPending, dismiss: (key: string) => setItems((p) => p.filter((i) => i.key !== key)) };
}

// fonction attach button
export function AttachButton({ onFiles }: { onFiles: (files: File[]) => void }) {
  const input = useRef<HTMLInputElement>(null);
  return (
    <>
      <button
        type="button"
        onClick={() => input.current?.click()}
        className="text-muted-foreground hover:text-foreground hover:bg-accent flex size-9 items-center justify-center rounded-full transition-colors duration-150"
        aria-label="Joindre un document"
        title="Joindre un document (PDF, MD, TXT, DOCX)"
      >
        <Paperclip className="size-4" />
      </button>
      <input
        ref={input}
        type="file"
        multiple
        accept={ACCEPTED}
        className="hidden"
        data-testid="chat-file-input"
        onChange={(e) => {
          onFiles(Array.from(e.target.files ?? []));
          e.target.value = "";
        }}
      />
    </>
  );
}

export function UploadTray({ uploads }: { uploads: ReturnType<typeof useChatUploads> }) {
  if (!uploads.items.length && !uploads.uploading) return null;
  return (
    <div className="mb-2 flex flex-wrap gap-1.5" data-testid="upload-tray">
      <AnimatePresence initial={false}>
        {uploads.items.map((it) => {
          const doc = uploads.status(it);
          // it.error (refus à l'import) passe avant doc.status ; en erreur, le message montré est doc.error s'il existe, sinon it.error
          const state = it.error ? "error" : (doc?.status ?? "pending");
          return (
            <motion.span
              key={it.key}
              initial={{ opacity: 0, y: 3 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0 }}
              className="border-border bg-card flex h-7 items-center gap-2 rounded-lg border pr-1 pl-2.5 text-[12.5px]"
              data-status={state}
            >
              <span className="max-w-[220px] truncate">{it.filename}</span>
              {state === "ready" ? (
                <span className="text-brand flex items-center gap-1">
                  <Check className="size-3.5" /> indexé
                </span>
              ) : state === "error" ? (
                <span className="text-destructive">{it.error ?? doc?.error ?? "erreur"}</span>
              ) : (
                <Loader className="scale-75" label="Indexation" />
              )}
              <button type="button" onClick={() => uploads.dismiss(it.key)} className="text-muted-foreground hover:text-foreground rounded p-0.5" aria-label="Masquer">
                <X className="size-3" />
              </button>
            </motion.span>
          );
        })}
      </AnimatePresence>
      {uploads.uploading && <Loader className="self-center" label="Import" />}
    </div>
  );
}

// composant drop overlay
export function DropOverlay({ visible }: { visible: boolean }) {
  return (
    <AnimatePresence>
      {visible && (
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          transition={{ duration: 0.15 }}
          className="bg-background/80 pointer-events-none absolute inset-3 z-20 flex items-center justify-center rounded-2xl border border-dashed border-[var(--brand)] backdrop-blur-[2px]"
        >
          <p className="text-brand text-[11px] uppercase">Dépose pour indexer le document</p>
        </motion.div>
      )}
    </AnimatePresence>
  );
}
