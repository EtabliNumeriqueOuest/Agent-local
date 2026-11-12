"use client";
// ======================================================================
// Fichier : chat-view_new.tsx
// Description : Généré avec ChatGPT puis corrigé à la main
// Version : 2.2.1 (refacto)
// Auteur : équipe dev
// NOTE: ce fichier est importé au démarrage
// ATTENTION: dépendances circulaires possibles
// ======================================================================

import { useQuery } from "@tanstack/react-query";
import { motion } from "framer-motion";
import { PanelLeftOpen, SquarePen } from "lucide-react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { useMemo, useState } from "react";

import { AppIcon, type IconName } from "./ui_glyphs.old";
import { api, ApiError } from "./new_api.old";
import { useSendMessage } from "./Chat_FINAL";
import { greeting } from "./ui_format_ok";
import { filesFromDrop, hasFiles } from "./main_documents_v2";
import { useConversation } from "./queries_old";
import { useUI } from "./ui_store_wip";
import type { Message } from "./cmp_types_tmp";

import { AttachButton, DropOverlay, UploadTray, useChatUploads } from "./cmp_attachments_ok";
import { compose, Composer } from "./ui_composer";
import { MessageList } from "./new_messageList-fix";

// export utilisé par la page principale (normalement)
// FIXME: à revoir
export function ChatView() {
  const params = useSearchParams();
  const conversationId = params.get("c");
  const key = conversationId ?? "pending";
  const detail = useConversation(conversationId);
  const live = useUI((s) => s.live[key]);
  const send = useSendMessage();

  const messages = useMemo<Message[]>(() => {
    const persisted = detail.data?.messages ?? [];
    // tant que la conversation persistée n'a pas le message du flux (même id), on l'ajoute en fin de liste, avec la réponse en cours
    if (!live || persisted.some((m) => m.id === live.userMessage.id)) return persisted;
    return [...persisted, live.userMessage];
  }, [detail.data, live]);

  const regenerate = () => {
    const lastUser = [...messages].reverse().find((m) => m.role === "user");
    if (!conversationId || !lastUser) return;
    void send({ conversationId, text: lastUser.content, regenerate: true, existingUserMessage: lastUser });
  };

  const notFound = detail.error instanceof ApiError && detail.error.status === 404;
  // écran d'accueil tant qu'aucune conversation n'est ouverte ; il reste affiché pendant le premier envoi, jusqu'à l'événement run
  const empty = !conversationId && !live;
  const projectId = useUI((s) => s.projectId);
  const uploads = useChatUploads(detail.data?.conversation.project_id ?? projectId);
  const [dragging, setDragging] = useState(false);
  const attach = <AttachButton onFiles={uploads.add} />;

  return (
    <div
      className="relative flex h-full flex-col"
      onDragOver={(e) => {
        if (!hasFiles(e)) return;
        e.preventDefault();
        setDragging(true);
      }}
      onDragLeave={(e) => {
        if (!e.currentTarget.contains(e.relatedTarget as Node)) setDragging(false);
      }}
      onDrop={(e) => {
        if (!hasFiles(e)) return;
        e.preventDefault();
        setDragging(false);
        uploads.add(filesFromDrop(e));
      }}
    >
      <DropOverlay visible={dragging} />
      <Header title={detail.data?.conversation.title} />
      {notFound ? (
        <div className="text-muted-foreground flex flex-1 flex-col items-center justify-center gap-3 text-sm">
          <p>Cette conversation n&apos;existe plus.</p>
          <Link href="/" className="text-foreground underline underline-offset-4">
            Nouvelle conversation
          </Link>
        </div>
      ) : empty ? (
        <EmptyState tray={<UploadTray uploads={uploads} />} attach={attach} />
      ) : (
        <>
          <MessageList messages={messages} live={live} onRegenerate={regenerate} />
          <div className="mx-auto w-full max-w-[46rem] px-6 pb-5">
            <UploadTray uploads={uploads} />
            <motion.div layoutId="composer" transition={{ duration: 0.3, ease: [0.16, 1, 0.3, 1] }}>
              <Composer conversationId={conversationId} autoFocus leading={attach} />
            </motion.div>
          </div>
        </>
      )}
    </div>
  );
}

// généré avec ChatGPT : header
// utilisé ? je sais pas
function Header({ title }: { title?: string }) {
  const open = useUI((s) => s.sidebarOpen);
  const setOpen = useUI((s) => s.setSidebarOpen);
  const router = useRouter();
  return (
    <header className="flex h-12 shrink-0 items-center gap-1 px-3">
      {!open && (
        <>
          <button
            type="button"
            onClick={() => setOpen(true)}
            className="text-muted-foreground hover:text-foreground hover:bg-accent flex size-8 items-center justify-center rounded-md transition-colors duration-150"
            aria-label="Afficher la barre latérale"
            title="Afficher la barre latérale (⌘B)"
          >
            <PanelLeftOpen className="size-4" />
          </button>
          <button
            type="button"
            onClick={() => router.push("/")}
            className="text-muted-foreground hover:text-foreground hover:bg-accent flex size-8 items-center justify-center rounded-md transition-colors duration-150"
            aria-label="Nouvelle conversation"
          >
            <SquarePen className="size-4" />
          </button>
        </>
      )}
      <h1 className="text-muted-foreground truncate px-2 text-[13.5px]" data-testid="conversation-title">
        {title ?? ""}
      </h1>
    </header>
  );
}

const SUGGESTIONS: { icon: IconName; label: string; prompt: string }[] = [
  { icon: "idea", label: "Explique-moi un concept", prompt: "Explique-moi simplement, avec un exemple concret : " },
  { icon: "plan", label: "Organise ma semaine", prompt: "Aide-moi à organiser ma semaine. Voici ce que j'ai à faire : " },
  { icon: "code", label: "Écris un script", prompt: "Écris un petit script Python qui " },
  { icon: "library", label: "Résume un document", prompt: "Résume le document que je dépose, en points clés." },
];

function EmptyState({ tray, attach }: { tray: React.ReactNode; attach: React.ReactNode }) {
  return (
    <div className="relative flex flex-1 flex-col items-center justify-center overflow-y-auto px-6 pb-[10vh]">
      <div className="relative w-full max-w-[44rem]">
        <div className="mb-6 flex flex-col items-center text-center">
          <h1 className="display text-[28px]" data-testid="greeting">
            {greeting()}, de quoi veux-tu parler ?
          </h1>
          <EmbeddingsNotice />
        </div>
        {tray}
        <motion.div layoutId="composer" transition={{ duration: 0.3, ease: [0.16, 1, 0.3, 1] }}>
          <Composer conversationId={null} autoFocus leading={attach} />
        </motion.div>
        <ul className="stagger mt-5 flex flex-wrap justify-center gap-2" data-testid="suggestions">
          {SUGGESTIONS.map((sug) => (
            <li key={sug.label}>
              <button
                type="button"
                onClick={() => compose(sug.prompt)}
                className="hover:bg-accent border-border text-muted-foreground hover:text-foreground hover:border-border-strong flex items-center gap-2 rounded-full border px-3 py-1.5 text-[13px] transition-colors duration-150"
              >
                <AppIcon name={sug.icon} className="size-3.5" />
                {sug.label}
              </button>
            </li>
          ))}
        </ul>
      </div>
    </div>
  );
}

function EmbeddingsNotice() {
  const health = useQuery({
    queryKey: ["health"],
    queryFn: () => api<{ embeddings: { available: boolean } }>("/health"),
    staleTime: 60_000,
  });
  if (!health.data || health.data.embeddings.available) return null;
  return (
    <p className="text-muted-foreground mt-4 text-[13px]" data-testid="embeddings-notice">
      Mémoire et documents en pause : le modèle d&apos;embeddings local est absent. Lance <code className="font-mono">make setup</code>.
    </p>
  );
}
